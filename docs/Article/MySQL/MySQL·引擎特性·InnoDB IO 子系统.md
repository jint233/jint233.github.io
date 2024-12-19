# MySQL · 引擎特性 · InnoDB IO子系统

## 前言

InnoDB做为一款成熟的跨平台数据库引擎，其实现了一套高效易用的IO接口，包括同步异步IO，IO合并等。本文简单介绍一下其内部实现，主要的代码集中在os0file.cc这个文件中。本文的分析默认基于MySQL 5.6，CentOS 6，gcc 4.8，其他版本的信息会另行指出。

## 基础知识

_ **WAL技术 :** _ 日志先行技术，基本所有的数据库，都使用了这个技术。简单的说，就是需要写数据块的时候，数据库前台线程把对应的日志先写（批量顺序写）到磁盘上，然后就告诉客户端操作成功，至于真正写数据块的操作（离散随机写）则放到后台IO线程中。使用了这个技术，虽然多了一个磁盘写入操作，但是由于日志是批量顺序写，效率很高，所以客户端很快就能得到相应。此外，如果在真正的数据块落盘之前，数据库奔溃，重启时候，数据库可以使用日志来做崩溃恢复，不会导致数据丢失。 _ **数据预读 :** _ 与数据块A“相邻”的数据块B和C在A被读取的时候，B和C也会有很大的概率被读取，所以可以在读取B的时候，提前把他们读到内存中，这就是数据预读技术。这里说的相邻有两种含义，一种是物理上的相邻，一种是逻辑上的相邻。底层数据文件中相邻，叫做物理上相邻。如果数据文件中不相邻，但是逻辑上相邻（id=1的数据和id=2的数据，逻辑上相邻，但是物理上不一定相邻，可能存在同一个文件中不同的位置），则叫逻辑相邻。 _ **文件打开模式 :** _ Open系统调用常见的模式主要三种：O_DIRECT，O_SYNC以及default模式。O_DIRECT模式表示后续对文件的操作不使用文件系统的缓存，用户态直接操作设备文件，绕过了内核的缓存和优化，从另外一个角度来说，使用O_DIRECT模式进行写文件，如果返回成功，数据就真的落盘了（不考虑磁盘自带的缓存），使用O_DIRECT模式进行读文件，每次读操作是真的从磁盘中读取，不会从文件系统的缓存中读取。O_SYNC表示使用操作系统缓存，对文件的读写都经过内核，但是这个模式还保证每次写数据后，数据一定落盘。default模式与O_SYNC模式类似，只是写数据后不保证数据一定落盘，数据有可能还在文件系统中，当主机宕机，数据有可能丢失。 此外，写操作不仅需要修改或者增加的数据落盘，而且还需要文件元信息落盘，只有两部分都落盘了，才能保证数据不丢。O_DIRECT模式不保证文件元信息落盘(但大部分文件系统都保证，Bug #45892)，因此如果不做其他操作，用O_DIRECT写文件后，也存在丢失的风险。O_SYNC则保证数据和元信息都落盘。default模式两种数据都不保证。 调用函数fsync后，能保证数据和日志都落盘，因此使用O_DIRECT和default模式打开的文件，写完数据，需要调用fsync函数。 _ **同步IO :** _ 我们常用的read/write函数（Linux上）就是这类IO，特点是，在函数执行的时候，调用者会等待函数执行完成，而且没有消息通知机制，因为函数返回了，就表示操作完成了，后续直接检查返回值就可知道操作是否成功。这类IO操作，编程比较简单，在同一个线程中就能完成所有操作，但是需要调用者等待，在数据库系统中，比较适合急需某些数据的时候调用，例如WAL中日志必须在返回客户端前落盘，则进行一次同步IO操作。 _ **异步IO :** _ 在数据库中，后台刷数据块的IO线程，基本都使用了异步IO。数据库前台线程只需要把刷块请求提交到异步IO的队列中即可返回做其他事情，而后台线程IO线程，则定期检查这些提交的请求是否已经完成，如果完成再做一些后续处理工作。同时异步IO由于常常是一批一批的请求提交，如果不同请求访问同一个文件且偏移量连续，则可以合并成一个IO请求。例如，第一个请求读取文件1，偏移量100开始的200字节数据，第二个请求读取文件1，偏移量300开始的100字节数据，则这两个请求可以合并为读取文件1，偏移量100开始的300字节数据。数据预读中的逻辑预读也常常使用异步IO技术。 目前Linux上的异步IO库，需要文件使用O_DIRECT模式打开，且数据块存放的内存地址、文件读写的偏移量和读写的数据量必须是文件系统逻辑块大小的整数倍，文件系统逻辑块大小可以使用类似`sudo blockdev --getss /dev/sda5`的语句查询。如果上述三者不是文件系统逻辑块大小的整数倍，则在调用读写函数时候会报错EINVAL，但是如果文件不使用O_DIRECT打开，则程序依然可以运行，只是退化成同步IO，阻塞在io_submit函数调用上。

## InnoDB常规IO操作以及同步IO

在InnoDB中，如果系统有pread/pwrite函数(`os_file_read_func`和`os_file_write_func`)，则使用它们进行读写，否则使用lseek+read/write方案。这个就是InnoDB同步IO。查看pread/pwrite文档可知，这两个函数不会改变文件句柄的偏移量且线程安全，所以多线程环境下推荐使用，而lseek+read/write方案则需要自己使用互斥锁保护，在高并发情况下，频繁的陷入内核态，对性能有一定影响。

在InnoDB中，使用open系统调用打开文件(`os_file_create_func`)，模式方面除了O_RDONLY(只读)，O_RDWR(读写)，O_CREAT(创建文件)外，还使用了O_EXCL(保证是这个线程创建此文件)和O_TRUNC(清空文件)。默认情况下(数据库不设置为只读模式)，所有文件都以O_RDWR模式打开。innodb_flush_method这个参数比较重要，重点介绍一下：

- 如果innodb_flush_method设置了O_DSYNC，日志文件(ib_logfileXXX)使用O_SYNC打开，因此写完数据不需要调用函数fsync刷盘，数据文件(ibd)使用default模式打开，因此写完数据需要调用fsync刷盘。
- 如果innodb_flush_method设置了O_DIRECT，日志文件(ib_logfileXXX)使用default模式打开，写完数据需要调用fsync函数刷盘，数据文件(ibd)使用O_DIRECT模式打开，写完数据需要调用fsync函数刷盘。
- 如果innodb_flush_method设置了fsync或者不设置，数据文件和日志文件都使用default模式打开，写完数据都需要使用fsync来刷盘。
- 如果innodb_flush_method设置为O_DIRECT_NO_FSYNC，文件打开方式与O_DIRECT模式类似，区别是，数据文件写完后，不调用fsync函数来刷盘，主要针对O_DIRECT能保证文件的元数据也落盘的文件系统。 InnoDB目前还不支持使用O_DIRECT模式打开日志文件，也不支持使用O_SYNC模式打开数据文件。 注意，如果使用linux native aio（详见下一节），innodb_flush_method一定要配置成O_DIRECT，否则会退化成同步IO（错误日志中不会有任务提示）。

InnoDB使用了文件系统的文件锁来保证只有一个进程对某个文件进行读写操作(`os_file_lock`)，使用了建议锁(Advisory locking)，而不是强制锁(Mandatory locking)，因为强制锁在不少系统上有bug，包括linux。在非只读模式下，所有文件打开后，都用文件锁锁住。

InnoDB中目录的创建使用递归的方式(`os_file_create_subdirs_if_needed`和`os_file_create_directory`)。例如，需要创建/a/b/c/这个目录，先创建c，然后b，然后a，创建目录调用mkdir函数。此外，创建目录上层需要调用`os_file_create_simple_func`函数，而不是`os_file_create_func`，需要注意一下。

InnoDB也需要临时文件，临时文件的创建逻辑比较简单(`os_file_create_tmpfile`)，就是在tmp目录下成功创建一个文件后直接使用unlink函数释放掉句柄，这样当进程结束后(不管是正常结束还是异常结束)，这个文件都会自动释放。InnoDB创建临时文件，首先复用了server层函数mysql_tmpfile的逻辑，后续由于需要调用server层的函数来释放资源，其又调用dup函数拷贝了一份句柄。

如果需要获取某个文件的大小，InnoDB并不是去查文件的元数据(`stat`函数)，而是使用`lseek(file, 0, SEEK_END)`的方式获取文件大小，这样做的原因是防止元信息更新延迟导致获取的文件大小有误。

InnoDB会预分配一个大小给所有新建的文件(包括数据和日志文件)，预分配的文件内容全部置为零(`os_file_set_size`)，当前文件被写满时，再进行扩展。此外，在日志文件创建时，即install_db阶段，会以100MB的间隔在错误日志中输出分配进度。

总体来说，常规IO操作和同步IO相对比较简单，但是在InnoDB中，数据文件的写入基本都用了异步IO。

## InnoDB异步IO

由于MySQL诞生在Linux native aio之前，所以在MySQL异步IO的代码中，有两种实现异步IO的方案。 第一种是原始的Simulated aio，InnoDB在Linux native air被import进来之前以及某些不支持air的系统上，自己模拟了一条aio的机制。异步读写请求提交时，仅仅把它放入一个队列中，然后就返回，程序可以去做其他事情。后台有若干异步io处理线程(innobase_read_io_threads和innobase_write_io_threads这两个参数控制)不断从这个队列中取出请求，然后使用同步IO的方式完成读写请求以及读写完成后的工作。 另外一种就是Native aio。目前在linux上使用io_submit，io_getevents等函数完成(不使用glibc aio，这个也是模拟的)。提交请求使用io_submit, 等待请求使用io_getevents。另外，window平台上也有自己对应的aio，这里就不介绍了，如果使用了window的技术栈，数据库应该会选用sqlserver。目前，其他平台(Linux和window之外)都只能使用Simulate aio。

首先介绍一下一些通用的函数和结构，接下来分别详细介绍一下Simulate alo和Linux上的Native aio。 在os0file.cc中定义了全局数组，类型为`os_aio_array_t`，这些数组就是Simulate aio用来缓存读写请求的队列，数组的每一个元素是`os_aio_slot_t`类型，里面记录了每个IO请求的类型，文件的fd，偏移量，需要读取的数据量，IO请求发起的时间，IO请求是否已经完成等。另外，Linux native io中的struct iocb也在`os_aio_slot_t`中。数组结构`os_aio_slot_t`中，记录了一些统计信息，例如有多少数据元素(`os_aio_slot_t`)已经被使用了，是否为空，是否为满等。这样的全局数组一共有5个，分别用来保存数据文件读异步请求(`os_aio_read_array`)，数据文件写异步请求(`os_aio_write_array`)，日志文件写异步请求(`os_aio_log_array`)，insert buffer写异步请求(`os_aio_ibuf_array`)，数据文件同步读写请求(`os_aio_sync_array`)。日志文件的数据块写入是同步IO，但是这里为什么还要给日志写分配一个异步请求队列(`os_aio_log_array`)呢？原因是，InnoDB日志文件的日志头中，需要记录checkpoint的信息，目前checkpoint信息的读写还是用异步IO来实现的，因为不是很紧急。在window平台中，如果对特定文件使用了异步IO，就这个文件就不能使用同步IO了，所以引入了数据文件同步读写请求队列(`os_aio_sync_array`)。日志文件不需要读异步请求队列，因为只有在做奔溃恢复的时候日志才需要被读取，而做崩溃恢复的时候，数据库还不可用，因此完全没必要搞成异步读取模式。这里有一点需要注意，不管变量innobase_read_io_threads和innobase_write_io_threads两个参数是多少，`os_aio_read_array`和`os_aio_write_array`都只有一个，只不过数据中的`os_aio_slot_t`元素会相应增加，在linux中，变量加1，元素数量增加256。例如，innobase_read_io_threads=4，则os_aio_read_array数组被分成了四部分，每一个部分256个元素，每个部分都有自己独立的锁、信号量以及统计变量，用来模拟4个线程，innobase_write_io_threads类似。从这里我们也可以看出，每个异步read/write线程能缓存的读写请求是有上限的，即为256，如果超过这个数，后续的异步请求需要等待。256可以理解为InnoDB层对异步IO并发数的控制，而在文件系统层和磁盘层面也有长度限制，分别使用`cat /sys/block/sda/queue/nr_requests`和`cat /sys/block/sdb/queue/nr_requests`查询。 `os_aio_init`在InnoDB启动的时候调用，用来初始化各种结构，包括上述的全局数组，还有Simulate aio中用的锁和互斥量。`os_aio_free`则释放相应的结构。`os_aio_print_XXX`系列的函数用来输出aio子系统的状态，主要用在`show engine innodb status`语句中。

### Simulate aio

Simulate aio相对Native aio来说，由于InnoDB自己实现了一套模拟机制，相对比较复杂。

- 入口函数为`os_aio_func`，在debug模式下，会校验一下参数，例如数据块存放的内存地址、文件读写的偏移量和读写的数据量是否是OS_FILE_LOG_BLOCK_SIZE的整数倍，但是没有检验文件打开模式是否用了O_DIRECT，因为Simulate aio最终都是使用同步IO，没有必要一定要用O_DIRECT打开文件。
- 校验通过后，就调用`os_aio_array_reserve_slot`，作用是把这个IO请求分配到某一个后台io处理线程(innobase_xxxx_io_threads分配的，但其实是在同一个全局数组中)中，并把io请求的相关信息记录下来，方便后台io线程处理。如果IO请求类型相同，请求同一个文件且偏移量比较接近(默认情况下，偏移量差别在1M内)，则InnoDB会把这两个请求分配到同一个io线程中，方便在后续步骤中IO合并。
- 提交IO请求后，需要唤醒后台io处理线程，因为如果后台线程检测到没有IO请求，会进入等待状态(`os_event_wait`)。
- 至此，函数返回，程序可以去干其他事情了，后续的IO处理交给后台线程了。 介绍一下后台IO线程怎么处理的。
- InnoDB启动时，后台IO线程会被启动(`io_handler_thread`)。其会调用`os_aio_simulated_handle`从全局数组中取出IO请求，然后用同步IO处理，结束后，需要做收尾工作，例如，如果是写请求的话，则需要在buffer pool中把对应的数据页从脏页列表中移除。
- `os_aio_simulated_handle`首先需要从数组中挑选出某个IO请求来执行，挑选算法并不是简单的先进先出，其挑选所有请求中offset最小的请求先处理，这样做是为了后续的IO合并比较方便计算。但是这也容易导致某些offset特别大的孤立请求长时间没有被执行到，也就是饿死，为了解决这个问题，在挑选IO请求之前，InnoDB会先做一次遍历，如果发现有请求是2s前推送过来的(也就是等待了2s)，但是还没有被执行，就优先执行最老的请求，防止这些请求被饿死，如果有两个请求等待时间相同，则选择offset小的请求。
- `os_aio_simulated_handle`接下来要做的工作就是进行IO合并，例如，读请求1请求的是file1，offset100开始的200字节，读请求2请求的是file1，offset300开始的100字节，则这两个请求可以合并为一个请求：file1，offset100开始的300字节，IO返回后，再把数据拷贝到原始请求的buffer中就可以了。写请求也类似，在写操作之前先把需要写的数据拷贝到一个临时空间，然后一次写完。注意，只有在offset连续的情况下IO才会合并，有间断或者重叠都不会合并，一模一样的IO请求也不会合并，所以这里可以算是一个可优化的点。
- `os_aio_simulated_handle`如果发现现在没有IO请求，就会进入等待状态，等待被唤醒

综上所述，可以看出IO请求是一个一个的push的对立面，每push进一个后台线程就拿去处理，如果后台线程优先级比较高的话，IO合并效果可能比较差，为了解决这个问题，Simulate aio提供类似组提交的功能，即一组IO请求提交后，才唤醒后台线程，让其统一进行处理，这样IO合并的效果会比较好。但这个依然有点小问题，如果后台线程比较繁忙的话，其就不会进入等待状态，也就是说只要请求进入了队列，就会被处理。这个问题在下面的Native aio中可以解决。 总体来说，InnoDB实现的这一套模拟机制还是比较安全可靠的，如果平台不支持Native aio则使用这套机制来读写数据文件。

### Linux native aio

如果系统安装了libaio库且在配置文件里面设置了innodb_use_native_aio=on则启动时候会使用Native aio。

- 入口函数依然为`os_aio_func`，在debug模式下，依然会检查传入的参数，同样不会检查文件是否以O_DIRECT模式打开，这算是一个有点风险的点，如果用户不知道linux native aio需要使用O_DIRECT模式打开文件才能发挥出aio的优势，那么性能就不会达到预期。建议在此处做一下检查，有问题输出到错误日志。
- 检查通过之后，与Simulated aio一样，调用`os_aio_array_reserve_slot`，把IO请求分配给后台线程，分配算法也考虑了后续的IO合并，与Simulated aio一样。不同之处，主要是需要用IO请求的参数初始化iocb这个结构。IO请求的相关信息除了需要初始化iocb外，也需要在全局数组的slot中记录一份，主要是为了在`os_aio_print_XXX`系列函数中统计方便。
- 调用io_submit提交请求。
- 至此，函数返回，程序可以去干其他事情了，后续的IO处理交给后台线程了。 接下来是后台IO线程。
- 与Simulate aio类似，后台IO线程也是在InnoDB启动时候启动。如果是Linux native aio，后续会调用`os_aio_linux_handle`这个函数。这个函数的作用与`os_aio_simulated_handle`类似，但是底层实现相对比较简单，其仅仅调用io_getevents函数等待IO请求完成。超时时间为0.5s，也就是说如果即使0.5内没有IO请求完成，函数也会返回，继续调用io_getevents等待，当然在等待前会判断一下服务器是否处于关闭状态，如果是则退出。

在分发IO线程时，尽量把相邻的IO放在一个线程内，这个与Simulate aio类似，但是后续的IO合并操作，Simulate aio是自己实现，Native aio则交给内核完成了，因此代码比较简单。 还要一个区别是，当没有IO请求的时候，Simulate aio会进入等待状态，而Native aio则会每0.5秒醒来一次，做一些检查工作，然后继续等待。因此，当有新的请求来时，Simulated aio需要用户线程唤醒，而Native aio不需要。此外，在服务器关闭时，Simulate aio也需要唤醒，Native aio则不需要。

可以发现，Native aio与Simulate aio类似，请求也是一个一个提交，然后一个一个处理，这样会导致IO合并效果比较差。Facebook团队提交了一个Native aio的组提交优化：把IO请求首先缓存，等IO请求都到了之后，再调用io_submit函数，一口气提交先前的所有请求(io_submit可以一次提交多个请求)，这样内核就比较方便做IO优化。Simulate aio在IO线程压力大的情况下，组提交优化会失效，而Native aio则不会。注意，组提交优化，不能一口气提交太多，如果超过了aio等待队列长度，会强制发起一次io_submit。

## 总结

本文详细介绍了InnoDB中IO子系统的实现以及使用需要注意的点。InnoDB日志使用同步IO，数据使用异步IO，异步IO的写盘顺序也不是先进先出的模式，这些点都需要注意。Simulate aio虽然有比较大的学习价值，但是在现代操作系统中，推荐使用Native aio。
