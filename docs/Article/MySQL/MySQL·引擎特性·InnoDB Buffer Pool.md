# MySQL・引擎特性・InnoDB Buffer Pool

## 前言

用户对数据库的最基本要求就是能高效的读取和存储数据，但是读写数据都涉及到与低速的设备交互，为了弥补两者之间的速度差异，所有数据库都有缓存池，用来管理相应的数据页，提高数据库的效率，当然也因为引入了这一中间层，数据库对内存的管理变得相对比较复杂。

本文主要分析 MySQL Buffer Pool 的相关技术以及实现原理，源码基于阿里云 RDS MySQL 5.6 分支，其中部分特性已经开源到 AliSQL。

Buffer Pool 相关的源代码在 buf 目录下，主要包括 **LRU List**，**Flu List**，**Double write buffer**, **预读预写**，**Buffer Pool 预热**，**压缩页内存管理** 等模块，包括头文件和 IC 文件，一共两万行代码。

## 基础知识

**Buffer Pool Instance:** 大小等于 innodb_buffer_pool_size/innodb_buffer_pool_instances，每个 instance 都有自己的锁，信号量，物理块 (Buffer chunks) 以及逻辑链表 (下面的各种 List)，即各个 instance 之间没有竞争关系，可以并发读取与写入。所有 instance 的物理块 (Buffer chunks) 在数据库启动的时候被分配，直到数据库关闭内存才予以释放。当 innodb_buffer_pool_size 小于 1GB 时候，innodb_buffer_pool_instances 被重置为 1，主要是防止有太多小的 instance 从而导致性能问题。每个 Buffer Pool Instance 有一个 page hash 链表，通过它，使用 space_id 和 page_no 就能快速找到已经被读入内存的数据页，而不用线性遍历 LRU List 去查找。

!!! Note "注意"
    这个 hash 表不是 InnoDB 的自适应哈希，自适应哈希是为了减少 Btree 的扫描，而 page hash 是为了避免扫描 LRU List。

**数据页：** InnoDB 中，数据管理的最小单位为页，默认是 16KB，页中除了存储用户数据，还可以存储控制信息的数据。InnoDB IO 子系统的读写最小单位也是页。如果对表进行了压缩，则对应的数据页称为压缩页，如果需要从压缩页中读取数据，则压缩页需要先解压，形成解压页，解压页为 16KB。压缩页的大小是在建表的时候指定，目前支持 16K，8K，4K，2K，1K。即使压缩页大小设为 16K，在 blob/varchar/text 的类型中也有一定好处。假设指定的压缩页大小为 4K，如果有个数据页无法被压缩到 4K 以下，则需要做 B-tree 分裂操作，这是一个比较耗时的操作。正常情况下，Buffer Pool 中会把压缩和解压页都缓存起来，当 Free List 不够时，按照系统当前的实际负载来决定淘汰策略。如果系统瓶颈在 IO 上，则只驱逐解压页，压缩页依然在 Buffer Pool 中，否则解压页和压缩页都被驱逐。

**Buffer Chunks:** 包括两部分：数据页和数据页对应的控制体，控制体中有指针指向数据页。Buffer Chunks 是最低层的物理块，在启动阶段从操作系统申请，直到数据库关闭才释放。通过遍历 chunks 可以访问几乎所有的数据页，有两种状态的数据页除外：没有被解压的压缩页 (BUF_BLOCK_ZIP_PAGE) 以及被修改过且解压页已经被驱逐的压缩页 (BUF_BLOCK_ZIP_DIRTY)。此外数据页里面不一定都存的是用户数据，开始是控制信息，比如行锁，自适应哈希等。

**逻辑链表:** 链表节点是数据页的控制体 (控制体中有指针指向真正的数据页)，链表中的所有节点都有同一的属性，引入其的目的是方便管理。下面其中链表都是逻辑链表。

**Free List:** 其上的节点都是未被使用的节点，如果需要从数据库中分配新的数据页，直接从上获取即可。InnoDB 需要保证 Free List 有足够的节点，提供给用户线程用，否则需要从 FLU List 或者 LRU List 淘汰一定的节点。InnoDB 初始化后，Buffer Chunks 中的所有数据页都被加入到 Free List，表示所有节点都可用。

**LRU List:** 这个是 InnoDB 中最重要的链表。所有新读取进来的数据页都被放在上面。链表按照最近最少使用算法排序，最近最少使用的节点被放在链表末尾，如果 Free List 里面没有节点了，就会从中淘汰末尾的节点。LRU List 还包含没有被解压的压缩页，这些压缩页刚从磁盘读取出来，还没来的及被解压。LRU List 被分为两部分，默认前 5/8 为 young list，存储经常被使用的热点 page，后 3/8 为 old list。新读入的 page 默认被加在 old list 头，只有满足一定条件后，才被移到 young list 上，主要是为了预读的数据页和全表扫描污染 buffer pool。

**FLU List:** 这个链表中的所有节点都是脏页，也就是说这些数据页都被修改过，但是还没来得及被刷新到磁盘上。在 FLU List 上的页面一定在 LRU List 上，但是反之则不成立。一个数据页可能会在不同的时刻被修改多次，在数据页上记录了最老 (也就是第一次) 的一次修改的 lsn，即 oldest_modification。不同数据页有不同的 oldest_modification，FLU List 中的节点按照 oldest_modification 排序，链表尾是最小的，也就是最早被修改的数据页，当需要从 FLU List 中淘汰页面时候，从链表尾部开始淘汰。加入 FLU List，需要使用 flush_list_mutex 保护，所以能保证 FLU List 中节点的顺序。

**Quick List:** 这个链表是阿里云 RDS MySQL 5.6 加入的，使用带 Hint 的 SQL 查询语句，可以把所有这个查询的用到的数据页加入到 Quick List 中，一旦这个语句结束，就把这个数据页淘汰，主要作用是避免 LRU List 被全表扫描污染。

**Unzip LRU List:** 这个链表中存储的数据页都是解压页，也就是说，这个数据页是从一个压缩页通过解压而来的。

**Zip Clean List:** 这个链表只在 Debug 模式下有，主要是存储没有被解压的压缩页。这些压缩页刚刚从磁盘读取出来，还没来的及被解压，一旦被解压后，就从此链表中删除，然后加入到 Unzip LRU List 中。

**Zip Free:** 压缩页有不同的大小，比如 8K，4K，InnoDB 使用了类似内存管理的伙伴系统来管理压缩页。Zip Free 可以理解为由 5 个链表构成的一个二维数组，每个链表分别存储了对应大小的内存碎片，例如 8K 的链表里存储的都是 8K 的碎片，如果新读入一个 8K 的页面，首先从这个链表中查找，如果有则直接返回，如果没有则从 16K 的链表中分裂出两个 8K 的块，一个被使用，另外一个放入 8K 链表中。

## 核心数据结构

InnoDB Buffer Pool 有三种核心的数据结构：buf_pool_t，buf_block_t，buf_page_t。

**but_pool_t:** 存储 Buffer Pool Instance 级别的控制信息，例如整个 Buffer Pool Instance 的 mutex，instance_no, page_hash，old_list_pointer 等。还存储了各种逻辑链表的链表根节点。Zip Free 这个二维数组也在其中。

**buf_block_t:** 这个就是数据页的控制体，用来描述数据页部分的信息 (大部分信息在 buf_page_t 中)。buf_block_t 中第一字段就是 buf_page_t，这个不是随意放的，是必须放在第一字段，因为只有这样 buf_block_t 和 buf_page_t 两种类型的指针可以相互转换。第二个字段是 frame 字段，指向真正存数据的数据页。buf_block_t 还存储了 Unzip LRU List 链表的根节点。另外一个比较重要的字段就是 block 级别的 mutex。

**buf_page_t:** 这个可以理解为另外一个数据页的控制体，大部分的数据页信息存在其中，例如 space_id, page_no, page state, newest_modification，oldest_modification，access_time 以及压缩页的所有信息等。压缩页的信息包括压缩页的大小，压缩页的数据指针 (真正的压缩页数据是存储在由伙伴系统分配的数据页上)。这里需要注意一点，如果某个压缩页被解压了，解压页的数据指针是存储在 buf_block_t 的 frame 字段里。

这里介绍一下 buf_page_t 中的 state 字段，这个字段主要用来表示当前页的状态。一共有八种状态。这八种状态对初学者可能比较难理解，尤其是前三种，如果看不懂可以先跳过。

**BUF_BLOCK_POOL_WATCH:** 这种类型的 page 是提供给 purge 线程用的。InnoDB 为了实现多版本，需要把之前的数据记录在 undo log 中，如果没有读请求再需要它，就可以通过 purge 线程删除。换句话说，purge 线程需要知道某些数据页是否被读取，现在解法就是首先查看 page hash，看看这个数据页是否已经被读入，如果没有读入，则获取 (启动时候通过 malloc 分配，不在 Buffer Chunks 中) 一个 BUF_BLOCK_POOL_WATCH 类型的哨兵数据页控制体，同时加入 page_hash 但是没有真正的数据 (buf_blokc_t::frame 为空) 并把其类型置为 BUF_BLOCK_ZIP_PAGE (表示已经被使用了，其他 purge 线程就不会用到这个控制体了)，相关函数 `buf_pool_watch_set`，如果查看 page hash 后发现有这个数据页，只需要判断控制体在内存中的地址是否属于 Buffer Chunks 即可，如果是表示对应数据页已经被其他线程读入了，相关函数 `buf_pool_watch_occurred`。另一方面，如果用户线程需要这个数据页，先查看 page hash 看看是否是 BUF_BLOCK_POOL_WATCH 类型的数据页，如果是则回收这个 BUF_BLOCK_POOL_WATCH 类型的数据页，从 Free List 中 (即在 Buffer Chunks 中) 分配一个空闲的控制体，填入数据。这里的核心思想就是通过控制体在内存中的地址来确定数据页是否还在被使用。

**BUF_BLOCK_ZIP_PAGE:** 当压缩页从磁盘读取出来的时候，先通过 malloc 分配一个临时的 buf_page_t，然后从伙伴系统中分配出压缩页存储的空间，把磁盘中读取的压缩数据存入，然后把这个临时的 buf_page_t 标记为 BUF_BLOCK_ZIP_PAGE 状态 (`buf_page_init_for_read`)，只有当这个压缩页被解压了，state 字段才会被修改为 BUF_BLOCK_FILE_PAGE，并加入 LRU List 和 Unzip LRU List (`buf_page_get_gen`)。如果一个压缩页对应的解压页被驱逐了，但是需要保留这个压缩页且压缩页不是脏页，则这个压缩页被标记为 BUF_BLOCK_ZIP_PAGE (`buf_LRU_free_page`)。所以正常情况下，处于 BUF_BLOCK_ZIP_PAGE 状态的不会很多。前述两种被标记为 BUF_BLOCK_ZIP_PAGE 的压缩页都在 LRU List 中。另外一个用法是，从 BUF_BLOCK_POOL_WATCH 类型节点中，如果被某个 purge 线程使用了，也会被标记为 BUF_BLOCK_ZIP_PAGE。

**BUF_BLOCK_ZIP_DIRTY:** 如果一个压缩页对应的解压页被驱逐了，但是需要保留这个压缩页且压缩页是脏页，则被标记为 BUF_BLOCK_ZIP_DIRTY (`buf_LRU_free_page`)，如果该压缩页又被解压了，则状态会变为 BUF_BLOCK_FILE_PAGE。因此 BUF_BLOCK_ZIP_DIRTY 也是一个比较短暂的状态。这种类型的数据页都在 Flush List 中。

**BUF_BLOCK_NOT_USED:** 当链表处于 Free List 中，状态就为此状态。是一个能长期存在的状态。

**BUF_BLOCK_READY_FOR_USE:** 当从 Free List 中，获取一个空闲的数据页时，状态会从 BUF_BLOCK_NOT_USED 变为 BUF_BLOCK_READY_FOR_USE (`buf_LRU_get_free_block`)，也是一个比较短暂的状态。处于这个状态的数据页不处于任何逻辑链表中。

**BUF_BLOCK_FILE_PAGE:** 正常被使用的数据页都是这种状态。LRU List 中，大部分数据页都是这种状态。压缩页被解压后，状态也会变成 BUF_BLOCK_FILE_PAGE。

**BUF_BLOCK_MEMORY:** Buffer Pool 中的数据页不仅可以存储用户数据，也可以存储一些系统信息，例如 InnoDB 行锁，自适应哈希索引以及压缩页的数据等，这些数据页被标记为 BUF_BLOCK_MEMORY。处于这个状态的数据页不处于任何逻辑链表中。

**BUF_BLOCK_REMOVE_HASH:** 当加入 Free List 之前，需要先把 page hash 移除。因此这种状态就表示此页面 page hash 已经被移除，但是还没被加入到 Free List 中，是一个比较短暂的状态。

总体来说，大部分数据页都处于 BUF_BLOCK_NOT_USED (全部在 Free List 中) 和 BUF_BLOCK_FILE_PAGE (大部分处于 LRU List 中，LRU List 中还包含除被 purge 线程标记的 BUF_BLOCK_ZIP_PAGE 状态的数据页) 状态，少部分处于 BUF_BLOCK_MEMORY 状态，极少处于其他状态。前三种状态的数据页都不在 Buffer Chunks 上，对应的控制体都是临时分配的，InnoDB 把他们列为 invalid state (`buf_block_state_valid`)。 如果理解了这八种状态以及其之间的转换关系，那么阅读 Buffer pool 的代码细节就会更加游刃有余。

接下来，简单介绍一下 buf_page_t 中 buf_fix_count 和 io_fix 两个变量，这两个变量主要用来做并发控制，减少 mutex 加锁的范围。当从 buffer pool 读取一个数据页时候，会其加读锁，然后递增 buf_page_t::buf_fix_count，同时设置 buf_page_t::io_fix 为 BUF_IO_READ，然后即可以释放读锁。后续如果其他线程在驱逐数据页 (或者刷脏) 的时候，需要先检查一下这两个变量，如果 buf_page_t::buf_fix_count 不为零且 buf_page_t::io_fix 不为 BUF_IO_NONE，则不允许驱逐 (`buf_page_can_relocate`)。这里的技巧主要是为了减少数据页控制体上 mutex 的争抢，而对数据页的内容，读取的时候依然要加读锁，修改时加写锁。

## Buffer Pool 内存初始化

Buffer Pool 的内存初始化，主要是 Buffer Chunks 的内存初始化，buffer pool instance 一个一个轮流初始化。核心函数为 `buf_chunk_init` 和 `os_mem_alloc_large` 。阅读代码可以发现，目前从操作系统分配内存有两种方式，一种是通过 HugeTLB 的方式来分配，另外一种使用传统的 mmap 来分配。

**HugeTLB:** 这是一种大内存块的分配管理技术。类似数据库对数据的管理，内存也按照页来管理，默认的页大小为 4KB，HugeTLB 就是把页大小提高到 2M 或者更加多。程序传送给 cpu 都是虚拟内存地址，cpu 必须通过快表来映射到真正的物理内存地址。快表的全集放在内存中，部分热点内存页可以放在 cpu cache 中，从而提高内存访问效率。

假设 cpu cache 为 100KB，每条快表占用 1KB，页大小为 4KB，则热点内存页为 100KB/1KB=100 条，覆盖 1004KB=400KB 的内存数据，但是如果也默认页大小为 2M，则同样大小的 cpu cache，可以覆盖 100\*2M=200MB 的内存数据，也就是说，访问 200MB 的数据只需要一次读取内存即可 (如果映射关系没有在 cache 中找到，则需要先把映射关系从内存中读到 cache，然后查找，最后再去读内存中需要的数据，会造成两次访问物理内存)。也就是说，使用 HugeTLB 这种大内存技术，可以提高快表的命中率，从而提高访问内存的性能。

当然这个技术也不是银弹，内存页变大了也必定会导致更多的页内的碎片。如果需要从 swap 分区中加载虚拟内存，也会变慢。当然最终要的理由是，4KB 大小的内存页已经被业界稳定使用很多年了，如果没有特殊的需求不需要冒这个风险。在 InnoDB 中，如果需要用到这项技术可以使用 super-large-pages 参数启动 MySQL。

**mmap 分配：** 在 Linux 下，多个进程需要共享一片内存，可以使用 mmap 来分配和绑定，所以只提供给一个 MySQL 进程使用也是可以的。用 mmap 分配的内存都是虚存，在 top 命令中占用 VIRT 这一列，而不是 RES 这一列，只有相应的内存被真正使用到了，才会被统计到 RES 中，提高内存使用率。这样是为什么常常看到 MySQL 一启动就被分配了很多的 VIRT，而 RES 却是慢慢涨上来的原因。这里大家可能有个疑问，为啥不用 malloc。其实查阅 malloc 文档，可以发现，当请求的内存数量大于 MMAP_THRESHOLD (默认为 128KB) 时候，malloc 底层就是调用了 mmap。在 InnoDB 中，默认使用 mmap 来分配。

分配完了内存，`buf_chunk_init` 函数中，把这片内存划分为两个部分，前一部分是数据页控制体 (buf_block_t)，在阿里云 RDS MySQL 5.6 release 版本中，每个 buf_block_t 是 424 字节，一共有 innodb_buffer_pool_size/UNIV_PAGE_SIZE 个。后一部分是真正的数据页，按照 UNIV_PAGE_SIZE 分隔。假设 page 大小为 16KB，则数据页控制体占的内存：数据页约等于 1:38.6，也就是说如果 innodb_buffer_pool_size 被配置为 40G，则需要额外的 1G 多空间来存数据页的控制体。

划分完空间后，遍历数据页控制体，设置 buf_block_t::frame 指针，指向真正的数据页，然后把这些数据页加入到 Free List 中即可。初始化完 Buffer Chunks 的内存，还需要初始化 BUF_BLOCK_POOL_WATCH 类型的数据页控制块，page hash 的结构体，zip hash 的结构体 (所有被压缩页的伙伴系统分配走的数据页面会加入到这个哈希表中)。注意这些内存是额外分配的，不包含在 Buffer Chunks 中。 除了 `buf_pool_init` 外，建议读者参考一下 `but_pool_free` 这个内存释放函数，加深对 Buffer Pool 相关内存的理解。

## Buf_page_get 函数解析

这个函数极其重要，是其他模块获取数据页的外部接口函数。如果请求的数据页已经在 Buffer Pool 中了，修改相应信息后，就直接返回对应数据页指针，如果 Buffer Pool 中没有相关数据页，则从磁盘中读取。`Buf_page_get` 是一个宏定义，真正的函数为 `buf_page_get_gen`，参数主要为 space_id, page_no, lock_type, mode 以及 mtr。这里主要介绍一个 mode 这个参数，其表示读取的方式，目前支持六种，前三种用的比较多。

**BUF_GET:** 默认获取数据页的方式，如果数据页不在 Buffer Pool 中，则从磁盘读取，如果已经在 Buffer Pool 中，需要判断是否要把他加入到 young list 中以及判断是否需要进行线性预读。如果是读取则加读锁，修改则加写锁。

**BUF_GET_IF_IN_POOL:** 只在 Buffer Pool 中查找这个数据页，如果在则判断是否要把它加入到 young list 中以及判断是否需要进行线性预读。如果不在则直接返回空。加锁方式与 BUF_GET 类似。

**BUF_PEEK_IF_IN_POOL:** 与 BUF_GET_IF_IN_POOL 类似，只是即使条件满足也不把它加入到 young list 中也不进行线性预读。加锁方式与 BUF_GET 类似。

**BUF_GET_NO_LATCH:** 不管对数据页是读取还是修改，都不加锁。其他方面与 BUF_GET 类似。

**BUF_GET_IF_IN_POOL_OR_WATCH:** 只在 Buffer Pool 中查找这个数据页，如果在则判断是否要把它加入到 young list 中以及判断是否需要进行线性预读。如果不在则设置 watch。加锁方式与 BUF_GET 类似。这个是要是给 purge 线程用。

**BUF_GET_POSSIBLY_FREED:** 这个 mode 与 BUF_GET 类似，只是允许相应的数据页在函数执行过程中被释放，主要用在估算 Btree 两个 slot 之前的数据行数。 接下来，我们简要分析一下这个函数的主要逻辑。

- 首先通过 `buf_pool_get` 函数依据 space_id 和 page_no 查找指定的数据页在那个 Buffer Pool Instance 里面。算法很简单 `instance_no = (space_id << 20 + space_id + page_no>> 6) % instance_num`，也就是说先通过 space_id 和 page_no 算出一个 fold value 然后按照 instance 的个数取余数即可。这里有个小细节，page_no 的第六位被砍掉，这是为了保证一个 extent 的数据能被缓存到同一个 Buffer Pool Instance 中，便于后面的预读操作。
  
- 接着，调用 `buf_page_hash_get_low` 函数在 page hash 中查找这个数据页是否已经被加载到对应的 Buffer Pool Instance 中，如果没有找到这个数据页且 mode 为 BUF_GET_IF_IN_POOL_OR_WATCH 则设置 watch 数据页 (`buf_pool_watch_set`)，接下来，如果没有找到数据页且 mode 为 BUF_GET_IF_IN_POOL、BUF_PEEK_IF_IN_POOL 或者 BUF_GET_IF_IN_POOL_OR_WATCH 函数直接返回空，表示没有找到数据页。如果没有找到数据但是 mode 为其他，就从磁盘中同步读取 (`buf_read_page`)。在读取磁盘数据之前，我们如果发现需要读取的是非压缩页，则先从 Free List 中获取空闲的数据页，如果 Free List 中已经没有了，则需要通过刷脏来释放数据页，这里的一些细节我们后续在 LRU 模块再分析，获取到空闲的数据页后，加入到 LRU List 中 (`buf_page_init_for_read`)。在读取磁盘数据之前，我们如果发现需要读取的是压缩页，则临时分配一个 buf_page_t 用来做控制体，通过伙伴系统分配到压缩页存数据的空间，最后同样加入到 LRU List 中 (`buf_page_init_for_read`)。做完这些后，我们就调用 IO 子系统的接口同步读取页面数据，如果读取数据失败，我们重试 100 次 (`BUF_PAGE_READ_MAX_RETRIES`) 然后触发断言，如果成功则判断是否要进行随机预读 (随机预读相关的细节我们也在预读预写模块分析)。

- 接着，读取数据成功后，我们需要判断读取的数据页是不是压缩页，如果是的话，因为从磁盘中读取的压缩页的控制体是临时分配的，所以需要重新分配 block (`buf_LRU_get_free_block`)，把临时分配的 buf_page_t 给释放掉，用 `buf_relocate` 函数替换掉，接着进行解压，解压成功后，设置 state 为 BUF_BLOCK_FILE_PAGE，最后加入 Unzip LRU List 中。

- 接着，我们判断这个页是否是第一次访问，如果是则设置 buf_page_t::access_time，如果不是，我们则判断其是不是在 Quick List 中，如果在 Quick List 中且当前事务不是加过 Hint 语句的事务，则需要把这个数据页从 Quick List 删除，因为这个页面被其他的语句访问到了，不应该在 Quick List 中了。

- 接着，如果 mode 不为 BUF_PEEK_IF_IN_POOL，我们需要判断是否把这个数据页移到 young list 中，具体细节在后面 LRU 模块中分析。

- 接着，如果 mode 不为 BUF_GET_NO_LATCH，我们给数据页加上读写锁。

- 最后，如果 mode 不为 BUF_PEEK_IF_IN_POOL 且这个数据页是第一次访问，则判断是否需要进行线性预读 (线性预读相关的细节我们也在预读预写模块分析)。

## LRU List 中 young list 和 old list 的维护

当 LRU List 链表大于 512 (`BUF_LRU_OLD_MIN_LEN`) 时，在逻辑上被分为两部分，前面部分存储最热的数据页，这部分链表称作 young list，后面部分则存储冷数据页，这部分称作 old list，一旦 Free List 中没有页面了，就会从冷页面中驱逐。两部分的长度由参数 innodb_old_blocks_pct 控制。每次加入或者驱逐一个数据页后，都要调整 young list 和 old list 的长度 (`buf_LRU_old_adjust_len`)，同时引入 `BUF_LRU_OLD_TOLERANCE` 来防止链表调整过频繁。当 LRU List 链表小于 512，则只有 old list。 新读取进来的页面默认被放在 old list 头，在经过 innodb_old_blocks_time 后，如果再次被访问了，就挪到 young list 头上。一个数据页被读入 Buffer Pool 后，在小于 innodb_old_blocks_time 的时间内被访问了很多次，之后就不再被访问了，这样的数据页也很快被驱逐。这个设计认为这种数据页是不健康的，应该被驱逐。

此外，如果一个数据页已经处于 young list，当它再次被访问的时候，不会无条件的移动到 young list 头上，只有当其处于 young list 长度的 1/4 (大约值) 之后，才会被移动到 young list 头部，这样做的目的是减少对 LRU List 的修改，否则每访问一个数据页就要修改链表一次，效率会很低，因为 LRU List 的根本目的是保证经常被访问的数据页不会被驱逐出去，因此只需要保证这些热点数据页在头部一个可控的范围内即可。相关逻辑可以参考函数 `buf_page_peek_if_too_old`。

## buf_LRU_get_free_block 函数解析

这个函数以及其调用的函数可以说是整个 LRU 模块最重要的函数，在整个 Buffer Pool 模块中也有举足轻重的作用。如果能把这几个函数吃透，相信其他函数很容易就能读懂。

- 首先，如果是使用 ENGINE_NO_CACHE 发送过来的 SQL 需要读取数据，则优先从 Quick List 中获取 (`buf_quick_lru_get_free`)。

- 接着，统计 Free List 和 LRU List 的长度，如果发现他们再 Buffer Chunks 占用太少的空间，则表示太多的空间被行锁，自使用哈希等内部结构给占用了，一般这些都是大事务导致的。这时候会给出报警。

- 接着，查看 Free List 中是否还有空闲的数据页 (`buf_LRU_get_free_only`)，如果有则直接返回，否则进入下一步。大多数情况下，这一步都能找到空闲的数据页。

- 如果 Free List 中已经没有空闲的数据页了，则会尝试驱逐 LRU List 末尾的数据页。如果系统有压缩页，情况就有点复杂，InnoDB 会调用 `buf_LRU_evict_from_unzip_LRU` 来决定是否驱逐压缩页，如果 Unzip LRU List 大于 LRU List 的十分之一或者当前 InnoDB IO 压力比较大，则会优先从 Unzip LRU List 中把解压页给驱逐，否则会从 LRU List 中把解压页和压缩页同时驱逐。不管走哪条路径，最后都调用了函数 `buf_LRU_free_page` 来执行驱逐操作，这个函数由于要处理压缩页解压页各种情况，极其复杂。大致的流程：首先判断是否是脏页，如果是则不驱逐，否则从 LRU List 中把链表删除，必要的话还从 Unzip LRU List 移走这个数据页 (`buf_LRU_block_remove_hashed`)，接着如果我们选择保留压缩页，则需要重新创建一个压缩页控制体，插入 LRU List 中，如果是脏的压缩页还要插入到 Flush List 中，最后才把删除的数据页插入到 Free List 中 (`buf_LRU_block_free_hashed_page`)。

- 如果在上一步中没有找到空闲的数据页，则需要刷脏了 (`buf_flush_single_page_from_LRU`)，由于 buf_LRU_get_free_block 这个函数是在用户线程中调用的，所以即使要刷脏，这里也是刷一个脏页，防止刷过多的脏页阻塞用户线程。

- 如果上一步的刷脏因为数据页被其他线程读取而不能刷脏，则重新跳转到上述第二步。进行第二轮迭代，与第一轮迭代的区别是，第一轮迭代在扫描 LRU List 时，最多只扫描 innodb_lru_scan_depth 个，而在第二轮迭代开始，扫描整个 LRU List。如果很不幸，这一轮还是没有找到空闲的数据页，从三轮迭代开始，在刷脏前等待 10ms。

- 最终找到一个空闲页后，page 的 state 为 BUF_BLOCK_READY_FOR_USE。

## 控制全表扫描不增加 cache 数据到 Buffer Pool

全表扫描对 Buffer Pool 的影响比较大，即使有 old list 作用，但是 old list 默认也占 Buffer Pool 的 3/8。因此，阿里云 RDS 引入新的语法 ENGINE_NO_CACHE (例如：SELECT ENGINE_NO_CACHE count (\*) FROM t1)。如果一个 SQL 语句中带了 ENGINE_NO_CACHE 这个关键字，则由它读入内存的数取据页都放入 Quick List 中，当这个语句结束时，会删除它独占的数据页。同时引入两个参数。innodb_rds_trx_own_block_max 这个参数控制使用 Hint 的每个事物最多能拥有多少个数据页，如果超过这个数据就开始驱逐自己已有的数据页，防止大事务占用过多的数据页。innodb_rds_quick_lru_limit_per_instance 这个参数控制每个 Buffer Pool Instance 中 Quick List 的长度，如果超过这个长度，后续的请求都从 Quick List 中驱逐数据页，进而获取空闲数据页。

## 删除指定表空间所有的数据页

函数 (`buf_LRU_remove_pages`) 提供了三种模式，第一种 (`BUF_REMOVE_ALL_NO_WRITE`)，删除 Buffer Pool 中所有这个类型的数据页 (LRU List 和 Flush List) 同时 Flush List 中的数据页也不写回数据文件，这种适合 rename table 和 5.6 表空间传输新特性，因为 space_id 可能会被复用，所以需要清除内存中的一切，防止后续读取到错误的数据。第二种 (`BUF_REMOVE_FLUSH_NO_WRITE`)，仅仅删除 Flush List 中的数据页同时 Flush List 中的数据页也不写回数据文件，这种适合 drop table，即使 LRU List 中还有数据页，但由于不会被访问到，所以会随着时间的推移而被驱逐出去。第三种 (`BUF_REMOVE_FLUSH_WRITE`)，不删除任何链表中的数据仅仅把 Flush List 中的脏页都刷回磁盘，这种适合表空间关闭，例如数据库正常关闭的时候调用。这里还有一点值得一提的是，由于对逻辑链表的变动需要加锁且删除指定表空间数据页这个操作是一个大操作，容易造成其他请求被饿死，所以 InnoDB 做了一个小小的优化，每删除 BUF_LRU_DROP_SEARCH_SIZE 个数据页 (默认为 1024) 就会释放一下 Buffer Pool Instance 的 mutex，便于其他线程执行。

## LRU_Manager_Thread

这是一个系统线程，随着 InnoDB 启动而启动，作用是定期清理出空闲的数据页 (数量为 innodb_LRU_scan_depth) 并加入到 Free List 中，防止用户线程去做同步刷脏影响效率。线程每隔一定时间去做 BUF_FLUSH_LRU，即首先尝试从 LRU 中驱逐部分数据页，如果不够则进行刷脏，从 Flush List 中驱逐 (`buf_flush_LRU_tail`)。线程执行的频率通过以下策略计算：我们设定 `max_free_len = innodb_LRU_scan_depth * innodb_buf_pool_instances`，如果 Free List 中的数量小于 max_free_len 的 1%，则 sleep time 为零，表示这个时候空闲页太少了，需要一直执行 buf_flush_LRU_tail 从而腾出空闲的数据页。如果 Free List 中的数量介于 max_free_len 的 1%-5%，则 sleep time 减少 50ms (默认为 1000ms)，如果 Free List 中的数量介于 max_free_len 的 5%-20%，则 sleep time 不变，如果 Free List 中的数量大于 max_free_len 的 20%，则 sleep time 增加 50ms，但是最大值不超过 `rds_cleaner_max_lru_time`。这是一个自适应的算法，保证在大压力下有足够用的空闲数据页 (`lru_manager_adapt_sleep_time`)。

## Hazard Pointer

在学术上，Hazard Pointer 是一个指针，如果这个指针被一个线程所占有，在它释放之前，其他线程不能对他进行修改，但是在 InnoDB 里面，概念刚好相反，一个线程可以随时访问 Hazard Pointer，但是在访问后，他需要调整指针到一个有效的值，便于其他线程使用。我们用 Hazard Pointer 来加速逆向的逻辑链表遍历。 先来说一下这个问题的背景，我们知道 InnoDB 中可能有多个线程同时作用在 Flush List 上进行刷脏，例如 LRU_Manager_Thread 和 Page_Cleaner_Thread。同时，为了减少锁占用的时间，InnoDB 在进行写盘的时候都会把之前占用的锁给释放掉。这两个因素叠加在一起导致同一个刷脏线程刷完一个数据页 A，就需要回到 Flush List 末尾 (因为 A 之前的脏页可能被其他线程给刷走了，之前的脏页可能已经不在 Flush list 中了)，重新扫描新的可刷盘的脏页。另一方面，数据页刷盘是异步操作，在刷盘的过程中，我们会把对应的数据页 IO_FIX 住，防止其他线程对这个数据页进行操作。我们假设某台机器使用了非常缓慢的机械硬盘，当前 Flush List 中所有页面都可以被刷盘 (`buf_flush_ready_for_replace` 返回 true)。我们的某一个刷脏线程拿到队尾最后一个数据页，IO fixed，发送给 IO 线程，最后再从队尾扫描寻找可刷盘的脏页。在这次扫描中，它发现最后一个数据页 (也就是刚刚发送到 IO 线程中的数据页) 状态为 IO fixed (磁盘很慢，还没处理完) 所以不能刷，跳过，开始刷倒数第二个数据页，同样 IO fixed，发送给 IO 线程，然后再次重新扫描 Flush List。它又发现尾部的两个数据页都不能刷新 (因为磁盘很慢，可能还没刷完)，直到扫描到倒数第三个数据页。所以，存在一种极端的情况，如果磁盘比较缓慢，刷脏算法性能会从 O (N) 退化成 O (N\*N)。

要解决这个问题，最本质的方法就是当刷完一个脏页的时候不要每次都从队尾重新扫描。我们可以使用 Hazard Pointer 来解决，方法如下：遍历找到一个可刷盘的数据页，在锁释放之前，调整 Hazard Pointer 使之指向 Flush List 中下一个节点，注意一定要在持有锁的情况下修改。然后释放锁，进行刷盘，刷完盘后，重新获取锁，读取 Hazard Pointer 并设置下一个节点，然后释放锁，进行刷盘，如此重复。当这个线程在刷盘的时候，另外一个线程需要刷盘，也是通过 Hazard Pointer 来获取可靠的节点，并重置下一个有效的节点。通过这种机制，保证每次读到的 Hazard Pointer 是一个有效的 Flush List 节点，即使磁盘再慢，刷脏算法效率依然是 O (N)。 这个解法同样可以用到 LRU List 驱逐算法上，提高驱逐的效率。相应的 Patch 是在 MySQL 5.7 上首次提出的，阿里云 RDS 把其 Port 到了我们 5.6 的版本上，保证在大并发情况下刷脏算法的效率。

## Page_Cleaner_Thread

这也是一个 InnoDB 的后台线程，主要负责 Flush List 的刷脏，避免用户线程同步刷脏页。与 LRU_Manager_Thread 线程相似，其也是每隔一定时间去刷一次脏页。其 sleep time 也是自适应的 (`page_cleaner_adapt_sleep_time`)，主要由三个因素影响：当前的 lsn，Flush list 中的 oldest_modification 以及当前的同步刷脏点 (`log_sys->max_modified_age_sync`，有 redo log 的大小和数量决定)。简单的来说，lsn - oldest_modification 的差值与同步刷脏点差距越大，sleep time 就越长，反之 sleep time 越短。此外，可以通过 `rds_page_cleaner_adaptive_sleep` 变量关闭自适应 sleep time，这是 sleep time 固定为 1 秒。 与 LRU_Manager_Thread 每次固定执行清理 innodb_LRU_scan_depth 个数据页不同，Page_Cleaner_Thread 每次执行刷的脏页数量也是自适应的，计算过程有点复杂 (`page_cleaner_flush_pages_if_needed`)。其依赖当前系统中脏页的比率，日志产生的速度以及几个参数。innodb_io_capacity 和 innodb_max_io_capacity 控制每秒刷脏页的数量，前者可以理解为一个 soft limit，后者则为 hard limit。innodb_max_dirty_pages_pct_lwm 和 innodb_max_dirty_pages_pct_lwm 控制脏页比率，即 InnoDB 什么脏页到达多少才算多了，需要加快刷脏频率了。innodb_adaptive_flushing_lwm 控制需要刷新到哪个 lsn。innodb_flushing_avg_loops 控制系统的反应效率，如果这个变量配置的比较大，则系统刷脏速度反应比较迟钝，表现为系统中来了很多脏页，但是刷脏依然很慢，如果这个变量配置很小，当系统中来了很多脏页后，刷脏速度在很短的时间内就可以提升上去。这个变量是为了让系统运行更加平稳，起到削峰填谷的作用。相关函数，`af_get_pct_for_dirty` 和 `af_get_pct_for_lsn`。

## 预读和预写

如果一个数据页被读入 Buffer Pool，其周围的数据页也有很大的概率被读入内存，与其分开多次读取，还不如一次都读入内存，从而减少磁盘寻道时间。在官方的 InnoDB 中，预读分两种，随机预读和线性预读。

**随机预读:** 这种预读发生在一个数据页成功读入 Buffer Pool 的时候 (`buf_read_ahead_random`)。在一个 Extent 范围 (1M，如果数据页大小为 16KB，则为连续的 64 个数据页) 内，如果热点数据页大于一定数量，就把整个 Extend 的其他所有数据页 (依据 page_no 从低到高遍历读入) 读入 Buffer Pool。这里有两个问题，首先数量是多少，默认情况下，是 13 个数据页。接着，怎么样的页面算是热点数据页，阅读代码发现，只有在 young list 前 1/4 的数据页才算是热点数据页。读取数据时候，使用了异步 IO，结合使用 `OS_AIO_SIMULATED_WAKE_LATER` 和 `os_aio_simulated_wake_handler_threads` 便于 IO 合并。随机预读可以通过参数 innodb_random_read_ahead 来控制开关。此外，`buf_page_get_gen` 函数的 mode 参数不影响随机预读。

**线性预读:** 这中预读只发生在一个边界的数据页 (Extend 中第一个数据页或者最后一个数据页) 上 (`buf_read_ahead_linear`)。在一个 Extend 范围内，如果大于一定数量 (通过参数 innodb_read_ahead_threshold 控制，默认为 56) 的数据页是被顺序访问 (通过判断数据页 access time 是否为升序或者逆序来确定) 的，则把下一个 Extend 的所有数据页都读入 Buffer Pool。读取的时候依然采用异步 IO 和 IO 合并策略。线性预读触发的条件比较苛刻，触发操作的是边界数据页同时要求其他数据页严格按照顺序访问，主要是为了解决全表扫描时的性能问题。线性预读可以通过参数 `innodb_read_ahead_threshold` 来控制开关。此外，当 `buf_page_get_gen` 函数的 mode 为 BUF_PEEK_IF_IN_POOL 时，不触发线性预读。

InnoDB 中除了有预读功能，在刷脏页的时候，也能进行预写 (`buf_flush_try_neighbors`)。当一个数据页需要被写入磁盘的时候，查找其前面或者后面邻居数据页是否也是脏页且可以被刷盘 (没有被 IOFix 且在 old list 中)，如果可以的话，一起刷入磁盘，减少磁盘寻道时间。预写功能可以通过 `innodb_flush_neighbors` 参数来控制。不过在现在的 SSD 磁盘下，这个功能可以关闭。

## Double Write Buffer(dblwr)

服务器突然断电，这个时候如果数据页被写坏了 (例如数据页中的目录信息被损坏)，由于 InnoDB 的 redolog 日志不是完全的物理日志，有部分是逻辑日志，因此即使奔溃恢复也无法恢复到一致的状态，只能依靠 Double Write Buffer 先恢复完整的数据页。Double Write Buffer 主要是解决数据页半写的问题，如果文件系统能保证写数据页是一个原子操作，那么可以把这个功能关闭，这个时候每个写请求直接写到对应的表空间中。

Double Write Buffer 大小默认为 2M，即 128 个数据页。其中分为两部分，一部分留给 batch write，另一部分是 single page write。前者主要提供给批量刷脏的操作，后者留给用户线程发起的单页刷脏操作。batch write 的大小可以由参数 `innodb_doublewrite_batch_size` 控制，例如假设 innodb_doublewrite_batch_size 配置为 120，则剩下 8 个数据页留给 single page write。 假设我们要进行批量刷脏操作，我们会首先写到内存中的 Double Write Buffer (也是 2M，在系统初始化中分配，不使用 Buffer Chunks 空间)，如果 dblwr 写满了，一次将其中的数据刷盘到系统表空间指定位置，注意这里是同步 IO 操作，在确保写入成功后，然后使用异步 IO 把各个数据页写回自己的表空间，由于是异步操作，所有请求下发后，函数就返回，表示写成功了 (`buf_dblwr_add_to_batch`)。不过这个时候后续的写请求依然会阻塞，知道这些异步操作都成功，才清空系统表空间上的内容，后续请求才能被继续执行。这样做的目的就是，如果在异步写回数据页的时候，系统断电，发生了数据页半写，这个时候由于系统表空间中的数据页是完整的，只要从中拷贝过来就行 (`buf_dblwr_init_or_load_pages`)。 异步 IO 请求完成后，会检查数据页的完整性以及完成 change buffer 相关操作，接着 IO helper 线程会调用 `buf_flush_write_complete` 函数，把数据页从 Flush List 删除，如果发现 batch write 中所有的数据页都写成了，则释放 dblwr 的空间。

## Buddy 伙伴系统

与内存分配管理算法类似，InnoDB 中的伙伴系统也是用来管理不规则大小内存分配的，主要用在压缩页的数据上。前文提到过，InnoDB 中的压缩页可以有 16K，8K，4K，2K，1K 这五种大小，压缩页大小的单位是表，也就是说系统中可能存在很多压缩页大小不同的表。使用伙伴体统来分配和回收，能提高系统的效率。

申请空间的函数是 `buf_buddy_alloc`，其首先在 zip free 链表中查看指定大小的块是否还存在，如果不存在则从更大的链表中分配，这回导致一些列的分裂操作。例如需要一块 4K 大小的内存，则先从 4K 链表中查找，如果有则直接返回，没有则从 8K 链表中查找，如果 8K 中还有空闲的，则把 8K 分成两部分，低地址的 4K 提供给用户，高地址的 4K 插入到 4K 的链表中，便与后续使用。如果 8K 中也没有空闲的了，就从 16K 中分配，16K 首先分裂成 2 个 8K，高地址的插入到 8K 链表中，低地址的 8K 继续分裂成 2 个 4K，低地址的 4K 返回给用户，高地址的 4K 插入到 4K 的链表中。假设 16K 的链表中也没有空闲的了，则调用 `buf_LRU_get_free_block` 获取新的数据页，然后把这个数据页加入到 zip hash 中，同时设置 state 状态为 BUF_BLOCK_MEMORY，表示这个数据页存储了压缩页的数据。

释放空间的函数是 `buf_buddy_free`，相比于分配空间的函数，有点复杂。假设释放一个 4K 大小的数据块，其先把 4K 放回 4K 对应的链表，接着会查看其伙伴 (释放块是低地址，则伙伴是高地址，释放块是高地址，则伙伴是低地址) 是否也被释放了，如果也被释放了则合并成 8K 的数据块，然后继续寻找这个 8K 数据块的伙伴，试图合并成 16K 的数据块。如果发现伙伴没有被释放，函数并不会直接退出而是把这个伙伴给挪走 (`buf_buddy_relocate`)，例如 8K 数据块的伙伴没有被释放，系统会查看 8K 的链表，如果有空闲的 8K 块，则把这个伙伴挪到这个空闲的 8K 上，这样就能合并成 16K 的数据块了，如果没有，函数才放弃合并并返回。通过这种 relocate 操作，内存碎片会比较少，但是涉及到内存拷贝，效率会比较低。

## Buffer Pool 预热

这个也是官方 5.6 提供的新功能，可以把当前 Buffer Pool 中的数据页按照 space_id 和 page_no dump 到外部文件，当数据库重启的时候，Buffer Pool 就可以直接恢复到关闭前的状态。

**Buffer Pool Dump:** 遍历所有 Buffer Pool Instance 的 LRU List，对于其中的每个数据页，按照 space_id 和 page_no 组成一个 64 位的数字，写到外部文件中即可 (`buf_dump`)。

**Buffer Pool Load:** 读取指定的外部文件，把所有的数据读入内存后，使用归并排序对数据排序，以 64 个数据页为单位进行 IO 合并，然后发起一次真正的读取操作。排序的作用就是便于 IO 合并 (`buf_load`)。

## 总结

InnoDB 的 Buffer Pool 可以认为很简单，就是 LRU List 和 Flush List，但是 InnoDB 对其做了很多性能上的优化，例如减少加锁范围，page hash 加速查找等，导致具体的实现细节相对比较复杂，尤其是引入压缩页这个特性后，有些核心代码变得晦涩难懂，需要读者细细琢磨。
