# MySQL · 引擎特性 · InnoDB 事务系统

## 前言

关系型数据库的事务机制因其有原子性，一致性等优秀特性深受开发者喜爱，类似的思想已经被应用到很多其他系统上，例如文件系统等。本文主要介绍 InnoDB 事务子系统，主要包括，事务的启动，事务的提交，事务的回滚，多版本控制，垃圾清理，回滚段以及相应的参数和监控方法。代码主要基于 RDS 5.6，部分特性已经开源到 AliSQL。事务系统是 InnoDB 最核心的中控系统，涉及的代码比较多，主要集中在 trx 目录，read 目录以及 row 目录中的一部分，包括头文件和 IC 文件，一共有两万两千多行代码。

## 基础知识

**事务 ACID:** 原子性，指的是整个事务要么全部成功，要么全部失败，对 InnoDB 来说，只要 client 收到 server 发送过来的 commit 成功报文，那么这个事务一定是成功的。如果收到的是 rollback 的成功报文，那么整个事务的所有操作一定都要被回滚掉，就好像什么都没执行过一样。另外，如果连接中途断开或者 server crash 事务也要保证会滚掉。InnoDB 通过 undo log 保证 rollback 的时候能找到之前的数据。一致性，指的是在任何时刻，包括数据库正常提供服务的时候，数据库从异常中恢复过来的时候，数据都是一致的，保证不会读到中间状态的数据。在 InnoDB 中，主要通过 crash recovery 和 double write buffer 的机制保证数据的一致性。隔离性，指的是多个事务可以同时对数据进行修改，但是相互不影响。InnoDB 中，依据不同的业务场景，有四种隔离级别可以选择。默认是 RR 隔离级别，因为相比于 RC，InnoDB 的 RR 性能更加好。持久性，值的是事务 commit 的数据在任何情况下都不能丢。在内部实现中，InnoDB 通过 redolog 保证已经 commit 的数据一定不会丢失。

**多版本控制:** 指的是一种提高并发的技术。最早的数据库系统，只有读读之间可以并发，读写，写读，写写都要阻塞。引入多版本之后，只有写写之间相互阻塞，其他三种操作都可以并行，这样大幅度提高了 InnoDB 的并发度。在内部实现中，与 Postgres 在数据行上实现多版本不同，InnoDB 是在 undo log 中实现的，通过 undo log 可以找回数据的历史版本。找回的数据历史版本可以提供给用户读(按照隔离级别的定义，有些读请求只能看到比较老的数据版本)，也可以在回滚的时候覆盖数据页上的数据。在 InnoDB 内部中，会记录一个全局的活跃读写事务数组，其主要用来判断事务的可见性。

**垃圾清理:** 对于用户删除的数据，InnoDB 并不是立刻删除，而是标记一下，后台线程批量的真正删除。类似的还有 InnoDB 的二级索引的更新操作，不是直接对索引进行更新，而是标记一下，然后产生一条新的。这个线程就是后台的 Purge 线程。此外，过期的 undo log 也需要回收，这里说的过期，指的是 undo 不需要被用来构建之前的版本，也不需要用来回滚事务。

**回滚段:** 可以理解为数据页的修改链，链表最前面的是最老的一次修改，最后面的最新的一次修改，从链表尾部逆向操作可以恢复到数据最老的版本。在 InnoDB 中，与之相关的还有 undo tablespace, undo segment, undo slot, undo log 这几个概念。undo log 是最小的粒度，所在的数据页称为 undo page，然后若干个 undo page 构成一个 undo slot。一个事务最多可以有两个 undo slot，一个是 insert undo slot, 用来存储这个事务的 insert undo，里面主要记录了主键的信息，方便在回滚的时候快速找到这一行。另外一个是 update undo slot，用来存储这个事务 delete/update 产生的 undo，里面详细记录了被修改之前每一列的信息，便于在读请求需要的时候构造。1024 个 undo slot 构成了一个 undo segment。然后若干个 undo segemnt 构成了 undo tablespace。

**历史链表:** insert undo 可以在事务提交/回滚后直接删除，没有事务会要求查询新插入数据的历史版本，但是 update undo 则不可以，因为其他读请求可能需要使用 update undo 构建之前的历史版本。因此，在事务提交的时候，会把 update undo 加入到一个全局链表(`history list`)中，链表按照事务提交的顺序排序，保证最先提交的事务的 update undo 在前面，这样 Purge 线程就可以从最老的事务开始做清理。这个链表如果太长说明有很多记录没被彻底删除，也有很多 undo log 没有被清理，这个时候就需要去看一下是否有个长事务没提交导致 Purge 线程无法工作。在 InnoDB 具体实现上，history list 其实只是 undo segment 维度的，全局的 history list 采用最小堆来实现，最小堆的元素是某个 undo segment 中最小事务 no 对应的 undo page。当这个 undo log 被 Purge 清理后，通过 history list 找到次小的，然后替换掉最小堆元素中的值，来保证下次 Purge 的顺序的正确性。

**回滚点:** 又称为 savepoint，事务回滚的时候可以指定回滚点，这样可以保证回滚到指定的点，而不是回滚掉整个事务，对开发者来说，这是一个强大的功能。在 InnoDB 内部实现中，每打一个回滚点，其实就是保存一下当前的 undo_no，回滚的时候直接回滚到这个 undo_no 点就可以了。

## 核心数据结构

在分析核心的代码之前，先介绍一下几个核心的数据结构。这些结构贯穿整个事务系统，理解他们对理解整个 InnoDB 的工作原理也颇有帮助。

**trx_t:** 整个结构体每个连接持有一个，也就是在创建连接后执行第一个事务开始，整个结构体就被初始化了，后续这个连接的所有事务一直复用里面的数据结构，直到这个连接断开。同时，事务启动后，就会把这个结构体加入到全局事务链表中(`trx_sys->mysql_trx_list`)，如果是读写事务，还会加入到全局读写事务链表中(`trx_sys->rw_trx_list`)。在事务提交的时候，还会加入到全局提交事务链表中(`trx_sys->trx_serial_list`)。state 字段记录了事务四种状态:`TRX_STATE_NOT_STARTED`, `TRX_STATE_ACTIVE`, `TRX_STATE_PREPARED`, `TRX_STATE_COMMITTED_IN_MEMORY`。 这里有两个字段值得区分一下，分别是 id 和 no 字段。id 是在事务刚创建的时候分配的(只读事务永远为 0，读写事务通过一个全局 id 产生器产生，非 0)，目的就是为了区分不同的事务(只读事务通过指针地址来区分)，而 no 字段是在事务提交前，通过同一个全局 id 生产器产生的，主要目的是为了确定事务提交的顺序，保证加入到`history list`中的 update undo 有序，方便 purge 线程清理。 此外，trx_t 结构体中还有自己的 read_view 用来表示当前事务的可见范围。分配的 insert undo slot 和 update undo slot。如果是只读事务，read_only 也会被标记为 true。

**trx_sys_t:** 这个结构体用来维护系统的事务信息，全局只有一个，在数据库启动的时候初始化。比较重要的字段有：max_trx_id，这个字段表示系统当前还未分配的最小事务 id，如果有一个新的事务，直接把这个值作为新事务的 id，然后这个字段递增即可。descriptors，这个是一个数组，里面存放着当前所有活跃的读写事务 id，当需要开启一个 read view 的时候，就从这个字段里面拷贝一份，用来判断记录的对事务的可见性。rw_trx_list，这个主要是用来存放当前系统的所有读写事务，包括活跃的和已经提交的事务。按照事务 id 排序，此外，奔溃恢复后产生的事务和系统的事务也放在上面。mysql_trx_list，这里面存放所有用户创建的事务，系统的事务和奔溃恢复后的事务不会在这个链表上，但是这个链表上可能会有还没开始的用户事务。trx_serial_list，按照事务 no(trx_t->no)排序的已经提交的事务。rseg_array，这个指向系统所有可以用的回滚段(`undo segments`)，当某个事务需要回滚段的时候，就从这里分配。rseg_history_len， 所有提交事务的 update undo 的长度，也就是上文提到的历史链表的长度，具体的 update undo 链表是存放在这个 undo log 中以文件指针的形式管理起来。view_list，这个是系统当前所有的 read view, 所有开启的 read view 的事务都会把自己的 read view 放在这个上面，按照事务 no 排序。

**trx_purge_t:** Purge 线程使用的结构体，全局只有一个，在系统启动的时候初始化。view，是一个 read view，Purge 线程不会尝试删除所有大于 view->low_limit_no 的 undo log。limit，所有小于这个值的 undo log 都可以被 truncate 掉，因为标记的日志已经被删除且不需要用他们构建之前的历史版本。此外，还有 rseg，page_no, offset，hdr_page_no, hdr_offset 这些字段，主要用来保存最后一个还未被 purge 的 undo log。

**read_view_t:** InnDB 为了判断某条记录是否对当前事务可见，需要对此记录进行可见性判断，这个结构体就是用来辅助判断的。每个连接都的 trx_t 里面都有一个 read view，在事务需要一致性的读时候(不同隔离级别不同)，会被初始化，在读结束的时候会释放(缓存)。low_limit_no，这个主要是给 purge 线程用，read view 创建的时候，会把当前最小的提交事务 id 赋值给 low_limit_no，这样 Purge 线程就可以把所有已经提交的事务的 undo 日志给删除。low_limit_id, 所有大于等于此值的记录都不应该被此 read view 看到，可以理解为 high water mark。up_limit_id, 所有小于此值的记录都应该被此 read view 看到，可以理解为 low water mark。descriptors, 这是一个数组，里面存了 read view 创建时候所有全局读写事务的 id，除了事务自己做的变更外，此 read view 应该看不到 descriptors 中事务所做的变更。view_list，每个 read view 都会被加入到 trx_sys 中的全局 read view 链表中。

**trx_id_t:** 每个读写事务都会通过全局 id 产生器产生一个 id，只读事务的事务 id 为 0，只有当其切换为读写事务时候再分配事务 id。为了保证在任何情况下(包括数据库不断异常恢复)，事务 id 都不重复，InnoDB 的全局 id 产生器每分配 256(`TRX_SYS_TRX_ID_WRITE_MARGIN`)个事务 id，就会把当前的 max_trx_id 持久化到 ibdata 的系统页上面。此外，每次数据库重启，都从系统页上读取，然后加上 256(`TRX_SYS_TRX_ID_WRITE_MARGIN`)。

**trx_rseg_t:** undo segment 内存中的结构体。每个 undo segment 都对应一个。update_undo_list 表示已经被分配出去的正在使用的 update undo 链表，insert_undo_list 表示已经被分配出去的正在使用的 insert undo 链表。update_undo_cached 和 insert_undo_cached 表示缓存起来的 undo 链表，主要为了快速使用。last_page_no, last_offset, last_trx_no, last_del_marks 表示这个 undo segment 中最后没有被 Purge 的 undo log。

## 事务的启动

在 InnoDB 里面有两种事务，一种是读写事务，就是会对数据进行修改的事务，另外一种是只读事务，仅仅对数据进行读取。读写事务需要比只读事务多做以下几点工作：首先，需要分配回滚段，因为会修改数据，就需要找地方把老版本的数据给记录下来，其次，需要通过全局事务 id 产生器产生一个事务 id，最后，把读写事务加入到全局读写事务链表(`trx_sys->rw_trx_list`)，把事务 id 加入到活跃读写事务数组中(`trx_sys->descriptors`)。因此，可以看出，读写事务确实需要比只读事务多做不少工作，在使用数据库的时候尽可能把事务申明为只读。

`start transaction`语句启动事务。这种语句和`begin work`,`begin`等效。这些语句默认是以只读事务的方式启动。`start transaction read only`语句启动事务。这种语句就把`thd->tx_read_only`置为 true，后续如果做了 DML/DDL 等修改数据的语句，会返回错误`ER_CANT_EXECUTE_IN_READ_ONLY_TRANSACTION`。`start transaction read write`语句启动事务。这种语句会把`thd->tx_read_only`置为 true，此外，允许 super 用户在 read_only 参数为 true 的情况下启动读写事务。`start transaction with consistent snapshot`语句启动事务。这种启动方式还会进入 InnoDB 层，并开启一个 read view。注意，只有在 RR 隔离级别下，这种操作才有效，否则会报错。

上述的几种启动方式，都会先去检查前一个事务是否已经提交，如果没有则先提交，然后释放 MDL 锁。此外，除了`with consistent snapshot`的方式会进入 InnoDB 层，其他所有的方式都只是在 Server 层做个标记，没有进入 InnoDB 做标记，在 InnoDB 看来所有的事务在启动时候都是只读状态，只有接受到修改数据的 SQL 后(InnoDB 接收到才行。因为在`start transaction read only`模式下，DML/DDL 都被 Serve 层挡掉了)才调用`trx_set_rw_mode`函数把只读事务提升为读写事务。

新建一个连接后，在开始第一个事务前，在 InnoDB 层会调用函数`innobase_trx_allocate`分配和初始化 trx_t 对象。默认的隔离级别为 REPEATABLE_READ，并且加入到`mysql_trx_list`中。注意这一步仅仅是初始化 trx_t 对象，但是真正开始事务的是函数`trx_start_low`，在`trx_start_low`中，如果当前的语句只是一条只读语句，则先以只读事务的形式开启事务，否则按照读写事务的形式，这就需要分配事务 id，分配回滚段等。

## 事务的提交

相比于事务的启动，事务的提交就复杂许多。这里只介绍事务在 InnoDB 层的提交过程，Server 层涉及到与 Binlog 的 XA 事务暂时不介绍。入口函数为`innobase_commit`。

函数有一个参数`commit_trx`来控制是否真的提交，因为每条语句执行结束的时候都会调用这个函数，而不是每条语句执行结束的时候事务都提交。如果这个参数为 true，或者配置了`autocommit=1`, 则进入提交的核心逻辑。否则释放因为 auto_inc 而造成的表锁，并且记录 undo_no(回滚单条语句的时候用到，相关参数`innodb_rollback_on_timeout`)。 提交的核心逻辑：

1. 依据参数 innobase_commit_concurrency 来判断是否有过多的线程同时提交，如果太多则等待。
2. 设置事务状态为 committing，我们可以在`show processlist`看到(`trx_commit_for_mysql`)。
3. 使用全局事务 id 产生器生成事务 no，然后把事务 trx_t 加入到`trx_serial_list`。如果当前的 undo segment 没有设置最后一个未 Purge 的 undo，则用此事务 no 更新(`trx_serialisation_number_get`)。
4. 标记 undo，如果这个事务只使用了一个 undo page 且使用量小于四分之三个 page，则把这个 page 标记为(`TRX_UNDO_CACHED`)。如果不满足且是 insert undo 则标记为`TRX_UNDO_TO_FREE`，否则 undo 为 update undo 则标记为`TRX_UNDO_TO_PURGE`。标记为`TRX_UNDO_CACHED`的 undo 会被回收，方便下次重新利用(`trx_undo_set_state_at_finish`)。
5. 把 update undo 放入所在 undo segment 的 history list，并递增`trx_sys->rseg_history_len`(这个值是全局的)。同时更新 page 上的`TRX_UNDO_TRX_NO`, 如果删除了数据，则重置 delete_mark(`trx_purge_add_update_undo_to_history`)。
6. 把 undate undo 从 update_undo_list 中删除，如果被标记为`TRX_UNDO_CACHED`，则加入到 update_undo_cached 队列中(`trx_undo_update_cleanup`)。
7. 在系统页中更新 binlog 名字和偏移量(`trx_write_serialisation_history`)。
8. mtr_commit，至此，在文件层次事务提交。这个时候即使 crash，重启后依然能保证事务是被提交的。接下来要做的是内存数据状态的更新(`trx_commit_in_memory`)。
9. 如果是只读事务，则只需要把 read view 从全局 read view 链表中移除，然后重置 trx_t 结构体里面的信息即可。如果是读写事务，情况则复杂点，首先需要是设置事务状态为`TRX_STATE_COMMITTED_IN_MEMORY`，其次，释放所有行锁，接着，trx_t 从 rw_trx_list 中移除，read view 从全局 read view 链表中移除，另外如果有 insert undo 则在这里移除(update undo 在事务提交前就被移除，主要是为了保证添加到 history list 的顺序)，如果有 update undo，则唤醒 Purge 线程进行垃圾清理，最后重置 trx_t 里的信息，便于下一个事务使用。

## 事务的回滚

InnoDB 的事务回滚是通过 undo log 来逆向操作来实现的，但是 undo log 是存在 undo page 中，undo page 跟普通的数据页一样，遵循 bufferpool 的淘汰机制，如果一个事务中的很多 undo page 已经被淘汰出内存了，那么在回滚的时候需要重新把这些 undo page 从磁盘中捞上来，这会造成大量 io，需要注意。此外，由于引入了 savepoint 的概念，事务不仅可以全部回滚，也可以回滚到某个指定点。

回滚的上层函数是`innobase_rollback_trx`，主要流程如下：

1. 如果是只读事务，则直接返回。
2. 判断当前是回滚整个事务还是部分事务，如果是部分事务，则记录下需要保留多少个 undo log，多余的都回滚掉，如果是全部回滚，则记录 0(trx_rollback_step)。
3. 从 update undo 和 insert undo 中找出最后一条 undo，从这条 undo 开始回滚(`trx_roll_pop_top_rec_of_trx`)。
4. 如果是 update undo 则调用`row_undo_mod`进行回滚，标记删除的记录清理标记，更新过的数据回滚到最老的版本。如果是 insert undo 则调用`row_undo_ins`进行回滚，插入操作，直接删除聚集索引和二级索引。
5. 如果是在奔溃恢复阶段且需要回滚的 undo log 个数大于 1000 条，则输出进度。
6. 如果所有 undo 都已经被回滚或者回滚到了指定的 undo，则停止，并且调用函数`trx_roll_try_truncate`把 undo log 删除(由于不需要使用 undo 构建历史版本，所以不需要留给 Purge 线程)。 此外，需要注意的是，回滚的代码由于是嵌入在 query graphy 的框架中，因此有些入口函数不太好找。例如，确定回滚范围的是在函数`trx_rollback_step`中，真正回滚的操作是在函数`row_undo_step`中，两者都是在函数`que_thr_step`被调用。

## 多版本控制 MVCC

数据库需要做好版本控制，防止不该被事务看到的数据(例如还没提交的事务修改的数据)被看到。在 InnoDB 中，主要是通过使用 read view 的技术来实现判断。查询出来的每一行记录，都会用 read view 来判断一下当前这行是否可以被当前事务看到，如果可以，则输出，否则就利用 undo log 来构建历史版本，再进行判断，知道记录构建到最老的版本或者可见性条件满足。

在 trx_sys 中，一直维护这一个全局的活跃的读写事务 id(`trx_sys->descriptors`)，id 按照从小到大排序，表示在某个时间点，数据库中所有的活跃(已经开始但还没提交)的读写(必须是读写事务，只读事务不包含在内)事务。当需要一个一致性读的时候(即创建新的 read view 时)，会把全局读写事务 id 拷贝一份到 read view 本地(read_view_t->descriptors)，当做当前事务的快照。read_view_t->up_limit_id 是 read_view_t->descriptors 这数组中最小的值，read_view_t->low_limit_id 是创建 read view 时的 max_trx_id，即一定大于 read_view_t->descriptors 中的最大值。当查询出一条记录后(记录上有一个 trx_id，表示这条记录最后被修改时的事务 id)，可见性判断的逻辑如下(`lock_clust_rec_cons_read_sees`)：

如果记录上的 trx_id 小于 read_view_t->up_limit_id，则说明这条记录的最后修改在 read view 创建之前，因此这条记录可以被看见。

如果记录上的 trx_id 大于等于 read_view_t->low_limit_id，则说明这条记录的最后修改在 read view 创建之后，因此这条记录肯定不可以被看家。

如果记录上的 trx_id 在 up_limit_id 和 low_limit_id 之间，且 trx_id 在 read_view_t->descriptors 之中，则表示这条记录的最后修改是在 read view 创建之时，被另外一个活跃事务所修改，所以这条记录也不可以被看见。如果 trx_id 不在 read_view_t->descriptors 之中，则表示这条记录的最后修改在 read view 创建之前，所以可以看到。

基于上述判断，如果记录不可见，则尝试使用 undo 去构建老的版本(`row_vers_build_for_consistent_read`)，直到找到可以被看见的记录或者解析完所有的 undo。 针对 RR 隔离级别，在第一次创建 read view 后，这个 read view 就会一直持续到事务结束，也就是说在事务执行过程中，数据的可见性不会变，所以在事务内部不会出现不一致的情况。针对 RC 隔离级别，事务中的每个查询语句都单独构建一个 read view，所以如果两个查询之间有事务提交了，两个查询读出来的结果就不一样。从这里可以看出，在 InnoDB 中，RR 隔离级别的效率是比 RC 隔离级别的高。此外，针对 RU 隔离级别，由于不会去检查可见性，所以在一条 SQL 中也会读到不一致的数据。针对串行化隔离级别，InnoDB 是通过锁机制来实现的，而不是通过多版本控制的机制，所以性能很差。

由于 read view 的创建涉及到拷贝全局活跃读写事务 id，所以需要加上 trx_sys->mutex 这把大锁，为了减少其对性能的影响，关于 read view 有很多优化。例如，如果前后两个查询之间，没有产生新的读写事务，那么前一个查询创建的 read view 是可以被后一个查询复用的。

## 垃圾回收 Purge 线程

Purge 线程主要做两件事，第一，数据页内标记的删除操作需要从物理上删除，为了提高删除效率和空间利用率，由后台 Purge 线程解析 undo log 定期批量清理。第二，当数据页上标记的删除记录已经被物理删除，同时 undo 所对应的记录已经能被所有事务看到，这个时候 undo 就没有存在的必要了，因此 Purge 线程还会把这些 undo 给 truncate 掉，释放更多的空间。

Purge 线程有两种，一种是 Purge Worker(`srv_worker_thread`), 另外一种是 Purge Coordinator(`srv_purge_coordinator_thread`)，前者的主要工作就是从队列中取出 Purge 任务，然后清理已经被标记的记录。后者的工作除了清理删除记录外，还需要把 Purge 任务放入队列，唤醒 Purge Worker 线程，此外，它还要 truncate undo log。

我们先来分析一下 Purge Coordinator 的流程。启动线程后，会进入一个大的循环，循环的终止条件是数据库关闭。在循环内部，首先是自适应的 sleep，然后才会进入核心 Purge 逻辑。sleep 时间与全局历史链表有关系，如果历史链表没有增长，且总数小于 5000，则进入 sleep，等待事务提交的时候被唤醒(`srv_purge_coordinator_suspend`)。退出循环后，也就是数据库进入关闭的流程，这个时候就需要依据参数 innodb_fast_shutdown 来确定在关闭前是否需要把所有记录给清除。接下来，介绍一下核心 Purge 逻辑。

1. 首先依据当前的系统负载来确定需要使用的 Purge 线程数(`srv_do_purge`)，即如果压力小，只用一个 Purge Cooridinator 线程就可以了。如果压力大，就多唤醒几个线程一起做清理记录的操作。如果全局历史链表在增加，或者全局历史链表已经超过`innodb_max_purge_lag`，则认为压力大，需要增加处理的线程数。如果数据库处于不活跃状态(`srv_check_activity`)，则减少处理的线程数。
2. 如果历史链表很长，超过`innodb_max_purge_lag`，则需要重新计算 delay 时间(不超过`innodb_max_purge_lag_delay`)。如果计算结果大于 0，则在后续的 DML 中需要先 sleep，保证不会太快产生 undo(`row_mysql_delay_if_needed`)。
3. 从全局视图链表中，克隆最老的 read view，所有在这个 read view 开启之前提交的事务所产生的 undo 都被认为是可以清理的。克隆之后，还需要把最老视图的创建者的 id 加入到`view->descriptors`中，因为这个事务修改产生的 undo，暂时还不能删除(`read_view_purge_open`)。
4. 从 undo segment 的最小堆中，找出最早提交事务的 undo log(`trx_purge_get_rseg_with_min_trx_id`)，如果 undo log 标记过 delete_mark(表示有记录删除操作)，则把先关 undo page 信息暂存在 purge_sys_t 中(`trx_purge_read_undo_rec`)。
5. 依据 purge_sys_t 中的信息，读取出相应的 undo，同时把相关信息加入到任务队列中。同时更新扫描过的指针，方便后续 truncate undo log。
6. 循环第 4 步和第 5 步，直到全局历史链表为空，或者接下到 view->low_limit_no，即最老视图创建时已经提交的事务，或者已经解析的 page 数量超过`innodb_purge_batch_size`。
7. 把所有的任务都放入队列后，就可以通知所有 Purge Worker 线程(如果有的话)去执行记录删除操作了。删除记录的核心逻辑在函数`row_purge_record_func`中。有两种情况，一种是数据记录被删除了，那么需要删除所有的聚集索引和二级索引(`row_purge_del_mark`)，另外一种是二级索引被更新了(总是先删除+插入新记录)，所以需要去执行清理操作。
8. 在所有提交的任务都已经被执行完后，就可以调用函数`trx_purge_truncate`去删除 update undo(insert undo 在事务提交后就被清理了)。每个 undo segment 分别清理，从自己的 histrory list 中取出最早的一个 undo，进行 truncate(`trx_purge_truncate_rseg_history`)。truncate 中，最终会调用`fseg_free_page`来清理磁盘上的空间。

## 事务的复活

在奔溃恢复后，也就是所有的前滚 redo 都应用完后，数据库需要做 undo 回滚，至于哪些事务需要提交，哪些事务需要回滚，这取决于 undo log 和 binlog 的状态。启动阶段，事务相关的代码逻辑主要在函数`trx_sys_init_at_db_start`中，简单分析一下。

1. 首先创建管理 undo segment 的最小堆，堆中的元素是每个 undo segment 提交最早的事务 id 和相应 undo segment 的指针，也就是说通过这个元素可以找到这个 undo segment 中最老的未被 Purge 的 undo。通过这个最小堆，可以找到所有 undo segment 中最老未被 Purge 的 undo，方便 Purge 线程操作。
2. 创建全局的活跃读写事务 id 数组。主要是给 read view 使用。
3. 初始化所有的 undo segment。主要是从磁盘读取 undo log 的内容，构建内存中的 undo slot 和 undo segment，同时也构建每个 undo segment 中的 history list，因为如果是 fast shutdown，被标记为删除的记录可能还没来得及被彻底清理。此外，也构建每个 undo segment 中的 inset_undo_list 和 update_undo_list，理论上来说，如果数据库关闭的时候所有事务都正常提交了，这两个链表都为空，如果数据库非正常关闭，则链表非空(`trx_undo_mem_create_at_db_start`, `trx_rseg_mem_create`)。
4. 从系统页里面读取 max_trx_id，然后加上 TRX_SYS_TRX_ID_WRITE_MARGIN 来保证 trx_id 不会重复，即使在很极端的情况下。
5. 遍历所有的 undo segment，针对每个 undo segment，分别遍历 inset_undo_list 和 update_undo_list，依据 undo 的状态来复活事务。
6. insert/update undo 的处理逻辑：如果 undo log 上的状态是`TRX_UNDO_ACTIVE`，则事务也被设置为`TRX_STATE_ACTIVE`，如果 undo log 上的状态是`TRX_UNDO_PREPARED`，则事务也被设置为`TRX_UNDO_PREPARED`(如果 force_recovery 不为 0，则设置为`TRX_STATE_ACTIVE`)。如果 undo log 状态是`TRX_UNDO_CACHED`,`TRX_UNDO_TO_FREE`,`TRX_UNDO_TO_PURGE`，那么都任务事务已经提交了(`trx_resurrect_insert`和`trx_resurrect_update`)。
7. 除了从 undo log 中复活出事务的状态信息，还需要复活出当前的锁信息(`trx_resurrect_table_locks`)，此外还需要把事务 trx_t 加入到 rw_trx_list 中。
8. 所有事务信息复活后，InnoDB 会做个统计，告诉你有多少 undo 需要做，因此可以在错误日志中看到类似的话: InnoDB: 120 transaction(s) which must be rolled back or cleaned up. InnoDB: in total 20M row operations to undo。
9. 如果事务中操作了数据字典，比如创建删除表和索引，则这个事务会在奔溃恢复结束后直接回滚，这个是个同步操作，会延长奔溃恢复的时间(`recv_recovery_from_checkpoint_finish`)。如果事务中没有操作数据字典，则后台会开启一个线程，异步回滚事务，所以我们常常发现，在数据库启动后，错误日志里面依然会有很多事务正在回滚的信息。

## 事务运维相关命令和参数

1. 首先介绍一下 information_schema 中的三张表: innodb_trx, innodb_locks 和 innodb_lock_waits。由于这些表几乎需要查询所有事务子系统的核心数据结构，为了减少查询对系统性能的影响，InnoDB 预留了一块内存，内存里面存了相关数据的副本，如果两次查询的时间小于 0.1 秒(`CACHE_MIN_IDLE_TIME_US`)，则访问的都是同一个副本。如果超过 0.1 秒，则这块内存会做一次更新，每次更新会把三张表用到的所有数据统一更新一遍，因为这三张表经常需要做表连接操作，所以一起更新能保证数据的一致性。这里简单介绍一下 innodb_trx 表中的字段，另外两张表涉及到事物锁的相关信息，由于篇幅限制，后续有机会在介绍。 trx_id: 就是 trx_t 中的事务 id，如果是只读事务，这个 id 跟 trx_t 的指针地址有关，所以可能是一个很大的数字(`trx_get_id_for_print`)。 trx_weight: 这个是事务的权重，计算方法就是 undo log 数量加上事务已经加上锁的数量。在事务回滚的时候，优先选择回滚权重小的事务，有非事务引擎参与的事务被认为权重是最大的。 trx_rows_modified：这个就是当前事务已经产生的 undo log 数量，每更新一条记录一次，就会产生一条 undo。 trx_concurrency_tickets: 每次这个事务需要进入 InnoDB 层时，这个值都会减一，如果减到 0，则事务需要等待(压力大的情况下)。 trx_is_read_only: 如果是以`start transaction read only`启动事务的，那么这个字段是 1，否则为 0。 trx_autocommit_non_locking: 如果一个事务是一个普通的 select 语句(后面没有跟 for update, share lock 等)，且当时的 autocommit 为 1，则这个字段为 1，否则为 0。 trx_state: 表示事务当前的状态，只能有`RUNNING`, `LOCK WAIT`, `ROLLING BACK`, `COMMITTING`这几种状态, 是比较粗粒度的状态。 trx_operation_state: 表示事务当前的详细状态，相比于 trx_state 更加详细，例如有`rollback to a savepoint`, `getting list of referencing foreign keys`, `rollback of internal trx on stats tables`, `dropping indexes`等。
2. 与事务相关的 undo 参数 innodb_undo_directory: undo 文件的目录，建议放在独立的一块盘上，尤其在经常有大事务的情况下。 innodb_undo_logs: 这个是定义了 undo segment 的个数。在给读写事务分配 undo segment 的时候，拿这个值去做轮训分配。 Innodb_available_undo_logs: 这个是一个 status 变量，在启动的时候就确定了，表示的是系统上分配的 undo segment。举个例子说明其与 innodb_undo_logs 的关系：假设系统初始化的时候 innodb_undo_logs 为 128，则在文件上一定有 128 个 undo segment，Innodb_available_undo_logs 也为 128，但是启动起来后，innodb_undo_logs 动态被调整为 100，则后续的读写事务只会使用到前 100 个回滚段，最后的 20 多个不会使用。 innodb_undo_tablespaces: 存放 undo segment 的物理文件个数，文件名为 undoN，undo segment 会比较均匀的分布在 undo tablespace 中。
3. 与 Purge 相关的参数 innodb_purge_threads: Purge Worker 和 Purge Coordinator 总共的个数。在实际的实现中，使用多少个线程去做 Purge 是 InnoDB 根据实时负载进行动态调节的。 innodb_purge_batch_size: 一次性处理的 undo log 的数量，处理完这个数量后，Purge 线程会计算是否需要 sleep。 innodb_max_purge_lag: 如果全局历史链表超过这个值，就会增加 Purge Worker 线程的数量，也会使用 sleep 的方式 delay 用户的 DML。 innodb_max_purge_lag_delay: 这个表示通过 sleep 方式 delay 用户 DML 最大的时间。
4. 与回滚相关的参数 innodb_lock_wait_timeout: 等待行锁的最大时间，如果超时，则会滚当前语句或者整个事务。发生回滚后返回类似错误：Lock wait timeout exceeded; try restarting transaction。 innodb_rollback_on_timeout: 如果这个参数为 true，则当发生因为等待行锁而产生的超时时，回滚掉整个事务，否则只回滚当前的语句。这个就是隐式回滚机制。主要是为了兼容之前的版本。

## 总结

本文简单介绍了 InnoDB 事务子系统的几个核心模块，在 MySQL 5.7 上，事务模块还有很多特性，例如高优先级事务，事务对象池等。与事务相关的还有事务锁系统，由于篇幅限制，本文不介绍，详情可以参考本期月报的这篇。此外，在阿里云最新发布的 POLARDB for MySQL 的版本中，由于涉及到共享存储架构，我们对事务子系统又进行了大量的改造，后续的月报会详细介绍。
