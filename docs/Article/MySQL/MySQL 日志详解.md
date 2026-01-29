# MySQL 日志详解

官方手册:[https://dev.mysql.com/doc/refman/5.7/en/server-logs.html](https://dev.mysql.com/doc/refman/5.7/en/server-logs.html)

不管是哪个数据库产品，一定会有日志文件。在 MariaDB/MySQL 中，主要有 5 种日志文件： 1.错误日志(error log)：记录 mysql 服务的启停时正确和错误的信息，还记录启动、停止、运行过程中的错误信息。 2.查询日志(general log)：记录建立的客户端连接和执行的语句。 3.二进制日志(bin log)：记录所有更改数据的语句，可用于数据复制。 4.慢查询日志(slow log)：记录所有执行时间超过 long_query_time 的所有查询或不使用索引的查询。 5.中继日志(relay log)：主从复制时使用的日志。

除了这 5 种日志，在需要的时候还会创建 DDL 日志。本文暂先讨论错误日志、一般查询日志、慢查询日志和二进制日志，中继日志和主从复制有关，将在复制的章节中介绍。下一篇文章将介绍 innodb 事务日志，见：[MySQL 的事务日志](https://www.cnblogs.com/f-ck-need-u/p/9010872.html)。

# 1.日志刷新操作

以下操作会刷新日志文件，刷新日志文件时会关闭旧的日志文件并重新打开日志文件。对于有些日志类型，如二进制日志，刷新日志会滚动日志文件，而不仅仅是关闭并重新打开。

```shell
mysql> FLUSH LOGS;
shell> mysqladmin flush-logs
shell> mysqladmin refresh
```

# 2.错误日志

错误日志是最重要的日志之一，它记录了 MariaDB/MySQL 服务启动和停止正确和错误的信息，还记录了 mysqld 实例运行过程中发生的错误事件信息。

可以使用" --log-error=[file_name] "来指定 mysqld 记录的错误日志文件，如果没有指定 file_name，则默认的错误日志文件为 datadir 目录下的 `hostname`.err ，hostname 表示当前的主机名。

也可以在 MariaDB/MySQL 配置文件中的 mysqld 配置部分，使用 log-error 指定错误日志的路径。

如果不知道错误日志的位置，可以查看变量 log_error 来查看。

```shell
mysql> show variables like 'log_error';
+---------------+----------------------------------------+
| Variable_name | Value                                  |
+---------------+----------------------------------------+
| log_error     | /var/lib/mysql/node1.longshuai.com.err |
+---------------+----------------------------------------+
```

在 MySQL 5.5.7 之前，刷新日志操作(如 flush logs)会备份旧的错误日志(以_old 结尾)，并创建一个新的错误日志文件并打开，在 MySQL 5.5.7 之后，执行刷新日志的操作时，错误日志会关闭并重新打开，如果错误日志不存在，则会先创建。

在 MariaDB/MySQL 正在运行状态下删除错误日志后，不会自动创建错误日志，只有在刷新日志的时候才会创建一个新的错误日志文件。

以下是 MySQL 5.6.35 启动的日志信息。

```shell
2017-03-29 01:15:14 2362 [Note] Plugin 'FEDERATED' is disabled.
2017-03-29 01:15:14 2362 [Note] InnoDB: Using atomics to ref count buffer pool pages
2017-03-29 01:15:14 2362 [Note] InnoDB: The InnoDB memory heap is disabled
2017-03-29 01:15:14 2362 [Note] InnoDB: Mutexes and rw_locks use GCC atomic builtins
2017-03-29 01:15:14 2362 [Note] InnoDB: Memory barrier is not used
2017-03-29 01:15:14 2362 [Note] InnoDB: Compressed tables use zlib 1.2.3
2017-03-29 01:15:14 2362 [Note] InnoDB: Using Linux native AIO
2017-03-29 01:15:14 2362 [Note] InnoDB: Using CPU crc32 instructions
2017-03-29 01:15:14 2362 [Note] InnoDB: Initializing buffer pool, size = 128.0M
2017-03-29 01:15:14 2362 [Note] InnoDB: Completed initialization of buffer pool
2017-03-29 01:15:14 2362 [Note] InnoDB: Highest supported file format is Barracuda.
2017-03-29 01:15:14 2362 [Note] InnoDB: 128 rollback segment(s) are active.
2017-03-29 01:15:14 2362 [Note] InnoDB: Waiting for purge to start
2017-03-29 01:15:14 2362 [Note] InnoDB: 5.6.35 started; log sequence number 3911610
2017-03-29 01:15:14 2362 [Note] Server hostname (bind-address): '*'; port: 3306
2017-03-29 01:15:14 2362 [Note] IPv6 is available.
2017-03-29 01:15:14 2362 [Note]   - '::' resolves to '::';
2017-03-29 01:15:14 2362 [Note] Server socket created on IP: '::'.
2017-03-29 01:15:14 2362 [Warning] 'proxies_priv' entry '@ [email protected]' ignored in --skip-name-resolve mode.
2017-03-29 01:15:14 2362 [Note] Event Scheduler: Loaded 0 events
2017-03-29 01:15:14 2362 [Note] /usr/local/mysql/bin/mysqld: ready for connections.
Version: '5.6.35'  socket: '/mydata/data/mysql.sock'  port: 3306  MySQL Community Server (GPL)
```

# 3.一般查询日志

查询日志分为一般查询日志和慢查询日志，它们是通过查询是否超出变量 long_query_time 指定时间的值来判定的。在超时时间内完成的查询是一般查询，可以将其记录到一般查询日志中，**但是建议关闭这种日志（默认是关闭的）**，超出时间的查询是慢查询，可以将其记录到慢查询日志中。

使用" --general_log={0|1} "来决定是否启用一般查询日志，使用" --general_log_file=file_name "来指定查询日志的路径。不给定路径时默认的文件名以 `hostname`.log 命名。

和查询日志有关的变量有：

```shell
`long_query_time = 10 ``# 指定慢查询超时时长，超出此时长的属于慢查询，会记录到慢查询日志中``log_output={TABLE|FILE|NONE}  ``# 定义一般查询日志和慢查询日志的输出格式，不指定时默认为file`
```

TABLE 表示记录日志到表中，FILE 表示记录日志到文件中，NONE 表示不记录日志。只要这里指定为 NONE，即使开启了一般查询日志和慢查询日志，也都不会有任何记录。

和一般查询日志相关的变量有：

```shell
`general_log=off ``# 是否启用一般查询日志，为全局变量，必须在global上修改。``sql_log_off=off ``# 在session级别控制是否启用一般查询日志，默认为off，即启用``general_log_file=``/mydata/data/hostname``.log  ``# 默认是库文件路径下主机名加上.log`
```

在 MySQL 5.6 以前的版本还有一个"log"变量也是决定是否开启一般查询日志的。在 5.6 版本开始已经废弃了该选项。

默认没有开启一般查询日志，也不建议开启一般查询日志。此处打开该类型的日志，看看是如何记录一般查询日志的。

首先开启一般查询日志。

```shell
mysql> set @@global.general_log=1;
ll *.log
-rw-rw---- 1 mysql mysql 5423 Mar 20 16:29 mysqld.log
-rw-rw---- 1 mysql mysql  262 Mar 29 09:31 xuexi.log
```

执行几个语句。

```shell
mysql> select host,user from mysql.user;
mysql> show variables like "%error%";
mysql> insert into ttt values(233);
mysql> create table tt(id int);
mysql> set @a:=3;
```

查看一般查询日志的内容。

```shell
cat xuexi.log 
/usr/local/mysql/bin/mysqld, Version: 5.6.35-log (MySQL Community Server (GPL)). started with:
Tcp port: 3306  Unix socket: /mydata/data/mysql.sock
Time                Id Command    Argument
180421 20:04:41     13 Query      select user,host from mysql.user
180421 20:06:06     13 Query      show variables like "%error%"
180421 20:07:28     13 Query      insert into ttt values(233)
180421 20:11:47     13 Query      create table tt(id int)
180421 20:12:29     13 Query      set @a:=3
```

由此可知，一般查询日志查询的不止是 select 语句，几乎所有的语句都会记录。

# 4.慢查询日志

查询超出变量 long_query_time 指定时间值的为慢查询。但是查询获取锁(包括锁等待)的时间不计入查询时间内。

mysql 记录慢查询日志是在查询执行完毕且已经完全释放锁之后才记录的，因此慢查询日志记录的顺序和执行的 SQL 查询语句顺序可能会不一致(例如语句 1 先执行，查询速度慢，语句 2 后执行，但查询速度快，则语句 2 先记录)。

注意，MySQL 5.1 之后就支持微秒级的慢查询超时时长，对于 DBA 来说，一个查询运行 0.5 秒和运行 0.05 秒是非常不同的，前者可能索引使用错误或者走了表扫描，后者可能索引使用正确。

另外，指定的慢查询超时时长表示的是超出这个时间的才算是慢查询，等于这个时间的不会记录。

和慢查询有关的变量：

```shell
`long_query_time=10 ``# 指定慢查询超时时长(默认10秒)，超出此时长的属于慢查询``log_output={TABLE|FILE|NONE} ``# 定义一般查询日志和慢查询日志的输出格式，默认为file``log_slow_queries={``yes``|no}    ``# 是否启用慢查询日志，默认不启用``slow_query_log={1|ON|0|OFF}  ``# 也是是否启用慢查询日志，此变量和log_slow_queries修改一个另一个同时变化``slow_query_log_file=``/mydata/data/hostname-slow``.log  ``#默认路径为库文件目录下主机名加上-slow.log``log_queries_not_using_indexes=OFF ``# 查询没有使用索引的时候是否也记入慢查询日志`
```

现在启用慢查询日志。

```shell
mysql> set @@global.slow_query_log=on;
```

因为默认超时时长为 10 秒，所以进行一个 10 秒的查询。

```shell
mysql> select sleep(10);
```

查看慢查询日志文件。这里看到虽然 sleep 了 10 秒，但是最后查询时间超出了 847 微秒，因此这里也记录了该查询。

```sql
cat xuexi-slow.log 
/usr/local/mysql/bin/mysqld, Version: 5.6.35-log (MySQL Community Server (GPL)). started with:
Tcp port: 3306  Unix socket: /mydata/data/mysql.sock
Time                 Id Command    Argument
# Time: 170329  9:55:58
# root[root] @ localhost []  Id:     1
# Query_time: 10.000847  Lock_time: 0.000000 Rows_sent: 1  Rows_examined: 0
use test;
SET timestamp=1490752558;
select sleep(10);
```

随着时间的推移，慢查询日志文件中的记录可能会变得非常多，这对于分析查询来说是非常困难的。好在提供了一个专门归类慢查询日志的工具 mysqldumpslow。

```shell
[root@xuexi data] mysqldumpslow --help
```

| 选项           | 说明                                                                                                                                                          |
|--------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `-d`         | Debug 模式：显示内部解析过程，用于调试。                                                                                                                                     |
| `-v`         | Verbose（详细）模式：显示每条查询的详细统计信息（如总时间、平均时间、锁定时间、返回行数等）。                                                                                                          |
| `-t NUM`     | Top N 查询：仅显示排序后最“突出”的前 `NUM` 条慢查询（默认按总耗时排序）。                                                                                                                |
| `-a`         | 禁用抽象归一化：<br>默认情况下，`mysqldumpslow` 会将 SQL 中的数字统一替换为 `N`，字符串替换为 `'S'`，以便合并相似语句（例如 `WHERE id = 100` 和 `WHERE id = 200` 被视为同一条）。<br>使用 `-a` 后，保留原始数值和字符串，不进行归类。 |
| `-g PATTERN` | 正则筛选（类似 grep）：<br>仅处理包含匹配 `PATTERN`（Perl 兼容正则表达式）的语句。<br>⚠️ 注意：并非仅用于筛选 `SELECT`，可匹配任意内容，如 `-g 'SELECT'`、`-g 'user_id'`、`-g '^UPDATE'` 等。                    |

该工具归类的时候，默认会将 **同文本但变量值不同的查询语句视为同一类，并使用 N 代替其中的数值变量，使用 S 代替其中的字符串变量**。可以使用-a 来禁用这种替换。如：

```shell
[root@xuexi data]# mysqldumpslow xuexi-slow.log 
Reading mysql slow query log from xuexi-slow.log
Count: 1  Time=10.00s (10s)  Lock=0.00s (0s)  Rows=1.0 (1), root[root]@localhost
  select sleep(N)

[root@xuexi data]#  mysqldumpslow -a xuexi-slow.log   
Reading mysql slow query log from xuexi-slow.log
Count: 1  Time=10.00s (10s)  Lock=0.00s (0s)  Rows=1.0 (1), root[root]@localhost
  select sleep(10)
```

显然，这里归类后的结果只是精确到 0.01 秒的，如果想要显示及其精确的秒数，则使用-d 选项启用调试功能。

```shell
[root@xuexi data]#  mysqldumpslow -d xuexi-slow.log   
Reading mysql slow query log from xuexi-slow.log
[[/usr/local/mysql/bin/mysqld, Version: 5.6.35-log (MySQL Community Server (GPL)). started with:
Tcp port: 3306  Unix socket: /mydata/data/mysql.sock
Time                 Id Command    Argument
# Time: 170329  9:55:58
# User@Host: root[root] @ localhost []  Id:     1
# Query_time: 10.000847  Lock_time: 0.000000 Rows_sent: 1  Rows_examined: 0
use test;
SET timestamp=1490752558;
select sleep(10);
]]
<<>>
<<# Time: 170329  9:55:58
# User@Host: root[root] @ localhost []  Id:     1
# Query_time: 10.000847  Lock_time: 0.000000 Rows_sent: 1  Rows_examined: 0
use test;
SET timestamp=1490752558;
select sleep(10);
>> at /usr/local/mysql/bin/mysqldumpslow line 97, <> chunk 1.
[[# Time: 170329  9:55:58
# User@Host: root[root] @ localhost []  Id:     1
# Query_time: 10.000847  Lock_time: 0.000000 Rows_sent: 1  Rows_examined: 0
use test;
SET timestamp=1490752558;
select sleep(10);
]]
{{  select sleep(N)}}

Count: 1  Time=10.00s (10s)  Lock=0.00s (0s)  Rows=1.0 (1), root[root]@localhost
  select sleep(N)
```

慢查询在 SQL 语句调优的时候非常有用，应该将它启用起来，且应该让慢查询阈值尽量小，例如 1 秒甚至低于 1 秒。就像一天执行上千次的 1 秒语句，和一天执行几次的 20 秒语句，显然更值得去优化这个 1 秒的语句。

# 5.二进制日志

## 5.1 二进制日志文件

二进制日志包含了 **引起或可能引起数据库改变** (如 delete 语句但没有匹配行)的事件信息，但绝不会包括 select 和 show 这样的查询语句。语句以"事件"的形式保存，所以包含了时间、事件开始和结束位置等信息。

二进制日志是 **以事件形式记录的，不是事务日志**  **(**  **但可能是基于事务来记录二进制日志)**，不代表它只记录 innodb 日志，myisam 表也一样有二进制日志。

对于事务表的操作，二进制日志 **只在事务提交的时候一次性写入**  **(**  **基于事务的 innodb**  **二进制日志)，提交前的每个二进制日志记录都先 cache，提交时写入**。

所以，对于事务表来说，一个事务中可能包含多条二进制日志事件，它们会在提交时一次性写入。而对于非事务表的操作，每次执行完语句就直接写入。

MariaDB/MySQL 默认没有启动二进制日志，要启用二进制日志使用 --log-bin=[on|off|file_name] 选项指定，如果没有给定 file_name，则默认为 datadir 下的主机名加"-bin"，并在后面跟上一串数字表示日志序列号，如果给定的日志文件中包含了后缀(logname.suffix)将忽略后缀部分。

![img](../assets/733013-20180507084125816-1681048114.png)

或者在配置文件中的[mysqld]部分设置 log-bin 也可以。注意：对于 mysql 5.7，直接启动 binlog 可能会导致 mysql 服务启动失败，这时需要在配置文件中的 mysqld 为 mysql 实例分配 server_id。

```shell
[mysqld]# server_id=1234``log-bin=[on|filename]`
```

mysqld 还 **创建一个二进制日志索引文件**，当二进制日志文件滚动的时候会向该文件中写入对应的信息。所以该文件包含所有使用的二进制日志文件的文件名。默认情况下该文件与二进制日志文件的文件名相同，扩展名为'.index'。要指定该文件的文件名使用 --log-bin-index[=file_name] 选项。当 mysqld 在运行时不应手动编辑该文件，免得 mysqld 变得混乱。

当重启 mysql 服务或刷新日志或者达到日志最大值时，将滚动二进制日志文件，滚动日志时只修改日志文件名的数字序列部分。

二进制日志文件的最大值通过变量 max_binlog_size 设置(默认值为 1G)。但由于二进制日志可能是基于事务来记录的(如 innodb 表类型)，而事务是绝对不可能也不应该跨文件记录的，如果正好二进制日志文件达到了最大值但事务还没有提交则不会滚动日志，而是继续增大日志，所以 max_binlog_size 指定的值和实际的二进制日志大小不一定相等。

因为二进制日志文件增长迅速，但官方说明因此而损耗的性能小于 1%，且二进制目的是为了恢复定点数据库和主从复制，所以出于安全和功能考虑，**极不建议将二进制日志和**  **datadir**  **放在同一磁盘上**。

## 5.2 查看二进制日志

MySQL 中查看二进制日志的方法主要有几种。

1.使用 mysqlbinlog 工具。

2.使用 show 显示对应的信息。

```plaintext
`SHOW {BINARY | MASTER} LOGS      ``# 查看使用了哪些日志文件``SHOW BINLOG EVENTS [IN ``'log_name'``] [FROM pos]   ``# 查看日志中进行了哪些操作``SHOW MASTER STATUS         ``# 显式主服务器中的二进制日志信息`
```

### 5.2.1 mysqlbinlog

二进制日志可以使用 mysqlbinlog 命令查看。

```plaintext
`mysqlbinlog [option] log-file1 log-file2...`
```

以下是常用的几个选项：

```plaintext
`-d,--database=name：只查看指定数据库的日志操作``-o,--offset=``#：忽略掉日志中的前n个操作命令``-r,--result-``file``=name：将输出的日志信息输出到指定的文件中，使用重定向也一样可以。``-s,--short-form：显示简单格式的日志，只记录一些普通的语句，会省略掉一些额外的信息如位置信息和时间信息以及基于行的日志。可以用来调试，生产环境千万不可使用``--``set``-charset=char_name：在输出日志信息到文件中时，在文件第一行加上``set` `names char_name``--start-datetime,--stop-datetime：指定输出开始时间和结束时间内的所有日志信息``--start-position=``#,--stop-position=#：指定输出开始位置和结束位置内的所有日志信息``-``v``,-vv：显示更详细信息，基于row的日志默认不会显示出来，此时使用-``v``或-vv可以查看`
```

在进行测试之前，先对日志进行一次刷新，以方便解释二进制日志的信息。

```plaintext
shell> mysqladmin -uroot -p refresh
```

假设现在的日志文件是 mysql-bin.000001，里面暂时只有一些初始信息，没有记录任何操作过的记录。

下面是每个二进制日志文件的初始信息。可以看到记录了时间和位置信息(at 4)。

```plaintext
[[email protected] data]# mysqlbinlog mysql-bin.000001 
/*!50530 SET @@SESSION.PSEUDO_SLAVE_MODE=1*/;
/*!40019 SET @@session.max_insert_delayed_threads=0*/;
/*!50003 SET @[email protected]@COMPLETION_TYPE,COMPLETION_TYPE=0*/;
DELIMITER /*!*/;
# at 4
#170329  2:18:10 server id 1  end_log_pos 120 CRC32 0x40f62523  Start: binlog v 4, server v 5.6.35-log created 170329  2:18:10 at startup
# Warning: this binlog is either in use or was not closed properly.
ROLLBACK/*!*/;
BINLOG '
4qjaWA8BAAAAdAAAAHgAAAABAAQANS42LjM1LWxvZwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAADiqNpYEzgNAAgAEgAEBAQEEgAAXAAEGggAAAAICAgCAAAACgoKGRkAASMl
9kA=
'/*!*/;
DELIMITER ;
# End of log file
ROLLBACK /* added by mysqlbinlog */;
/*!50003 SET [email protected]_COMPLETION_TYPE*/;
/*!50530 SET @@SESSION.PSEUDO_SLAVE_MODE=0*/;
```

现在在数据库中执行下面的操作：

```sql
use test;
create table student(studentid int not null primary key,name varchar(30) not null,gender enum('female','mail'));
alter table student change gender gender enum('female','male');
insert into student values(1,'malongshuai','male'),(2,'gaoxiaofang','female');
```

再查看二进制日志信息。

```sql
[[email protected] data]# mysqlbinlog mysql-bin.000001 
/*!50530 SET @@SESSION.PSEUDO_SLAVE_MODE=1*/;
/*!40019 SET @@session.max_insert_delayed_threads=0*/;
/*!50003 SET @[email protected]@COMPLETION_TYPE,COMPLETION_TYPE=0*/;
DELIMITER /*!*/;
# at 4
#170329  2:18:10 server id 1  end_log_pos 120 CRC32 0x40f62523  Start: binlog v 4, server v 5.6.35-log created 170329  2:18:10 at startup
# Warning: this binlog is either in use or was not closed properly.
ROLLBACK/*!*/;
BINLOG '
4qjaWA8BAAAAdAAAAHgAAAABAAQANS42LjM1LWxvZwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAADiqNpYEzgNAAgAEgAEBAQEEgAAXAAEGggAAAAICAgCAAAACgoKGRkAASMl
9kA=
'/*!*/;
# at 120
#170329  5:20:00 server id 1  end_log_pos 305 CRC32 0xbac43912  Query   thread_id=1     exec_time=0     error_code=0
use `test`/*!*/;
SET TIMESTAMP=1490736000/*!*/;
SET @@session.pseudo_thread_id=1/*!*/;
SET @@session.foreign_key_checks=1, @@session.sql_auto_is_null=0, @@session.unique_checks=1, @@session.autocommit=1/*!*/;
SET @@session.sql_mode=1075838976/*!*/;
SET @@session.auto_increment_increment=1, @@session.auto_increment_offset=1/*!*/;
/*!\C utf8 *//*!*/;
SET @@session.character_set_client=33,@@session.collation_connection=33,@@session.collation_server=8/*!*/;
SET @@session.lc_time_names=0/*!*/;
SET @@session.collation_database=DEFAULT/*!*/;
create table student(studentid int not null primary key,name varchar(30) not null,gender enum('female','mail'))
/*!*/;
# at 305
#170329  5:21:21 server id 1  end_log_pos 441 CRC32 0xde67f702  Query   thread_id=1     exec_time=0     error_code=0
SET TIMESTAMP=1490736081/*!*/;
alter table student change gender gender enum('female','male')
/*!*/;
# at 441
#170329  5:21:33 server id 1  end_log_pos 520 CRC32 0x05a9c5a1  Query   thread_id=1     exec_time=0     error_code=0
SET TIMESTAMP=1490736093/*!*/;
BEGIN
/*!*/;
# at 520
#170329  5:21:33 server id 1  end_log_pos 671 CRC32 0xad9e7dc8  Query   thread_id=1     exec_time=0     error_code=0
SET TIMESTAMP=1490736093/*!*/;
insert into student values(1,'malongshuai','male'),(2,'gaoxiaofang','female')
/*!*/;
# at 671
#170329  5:21:33 server id 1  end_log_pos 702 CRC32 0xb69b0f7d  Xid = 32
COMMIT/*!*/;
DELIMITER ;
# End of log file
ROLLBACK /* added by mysqlbinlog */;
/*!50003 SET [email protected]_COMPLETION_TYPE*/;
/*!50530 SET @@SESSION.PSEUDO_SLAVE_MODE=0*/; 
```

将上述信息整理为下图：其中 timestamp 记录的是从 1970-01-01 到现在的总秒数时间戳，可以使用 date -d '@1490736093' 转换。

![img](../assets/733013-20180507085958196-1633846460.png)

- 位置 0-120 记录的是二进制日志的一些固定信息。
- 位置 120-305 记录的是 use 和 create table 语句，语句的记录时间为 5:20:00。但注意，这里的 use 不是执行的 use 语句，而是 MySQL 发现要操作的数据库为 test，而自动进行的操作并记录下来。人为的 use 语句是不会记录的。
- 位置 305-441 记录的是 alter table 语句，语句的记录时间为 5:20:21。
- 位置 441-702 记录的是 insert 操作，因为该操作是 DML 语句，因此记录了事务的开始 BEGIN 和提交 COMMIT。
  - begin 的起止位置为 441-520；
  - insert into 语句的起止位置为 520-671，记录的时间和自动开启事务的 begin 时间是一样的；
  - commit 的起止位置为 671-702。

使用-r 命令将日志文件导入到指定文件中，使用重定向也可以实现同样的结果。并使用-s 查看简化的日志文件。

```plaintext
[[email protected] data]# mysqlbinlog mysql-bin.000001 -r /tmp/binlog.000001
[[email protected] data]# mysqlbinlog mysql-bin.000001 -s>/tmp/binlog.sample
```

比较这两个文件，看看简化的日志文件简化了哪些东西。

![img](../assets/733013-20180507090446176-118990478.png)

从上图中可以看出，使用-s 后，少了基于行的日志信息，也少了记录的位置和时间信息。

使用-o 可以忽略前 N 个条目，例如上面的操作涉及了 6 个操作。忽略掉前 3 个后的日志显示如下：可以看到直接从位置 441 开始显示了。

```sql
[[email protected] data]# mysqlbinlog mysql-bin.000001 -o 3
...前面固定部分省略...
'/*!*/;
# at 441
#170329  5:21:33 server id 1  end_log_pos 520 CRC32 0x05a9c5a1  Query   thread_id=1     exec_time=0     error_code=0
SET TIMESTAMP=1490736093/*!*/;
SET @@session.pseudo_thread_id=1/*!*/;
SET @@session.foreign_key_checks=1, @@session.sql_auto_is_null=0, @@session.unique_checks=1, @@session.autocommit=1/*!*/;
SET @@session.sql_mode=1075838976/*!*/;
SET @@session.auto_increment_increment=1, @@session.auto_increment_offset=1/*!*/;
/*!\C utf8 *//*!*/;
SET @@session.character_set_client=33,@@session.collation_connection=33,@@session.collation_server=8/*!*/;
SET @@session.lc_time_names=0/*!*/;
SET @@session.collation_database=DEFAULT/*!*/;
BEGIN
/*!*/;
# at 520
#170329  5:21:33 server id 1  end_log_pos 671 CRC32 0xad9e7dc8  Query   thread_id=1     exec_time=0     error_code=0
use `test`/*!*/;
SET TIMESTAMP=1490736093/*!*/;
insert into student values(1,'malongshuai','male'),(2,'gaoxiaofang','female')
/*!*/;
# at 671
#170329  5:21:33 server id 1  end_log_pos 702 CRC32 0xb69b0f7d  Xid = 32
COMMIT/*!*/;
DELIMITER ;
...后面固定部分省略... 
```

使用-d 可以只显示指定数据库相关的操作。例如先切换到其他数据库进行一番操作，然后再使用-d 查看日志。

```sql
mysql> use mysql;
mysql> create table mytest(id int);
[[email protected] data]# mysqlbinlog mysql-bin.000001 -d mysql
...前固定部分省略...'/*!*/;
# at 120
# at 305
# at 441
#170329  5:21:33 server id 1  end_log_pos 520 CRC32 0x05a9c5a1  Query   thread_id=1     exec_time=0     error_code=0
SET TIMESTAMP=1490736093/*!*/;
SET @@session.pseudo_thread_id=1/*!*/;
SET @@session.foreign_key_checks=1, @@session.sql_auto_is_null=0, @@session.unique_checks=1, @@session.autocommit=1/*!*/;
SET @@session.sql_mode=1075838976/*!*/;
SET @@session.auto_increment_increment=1, @@session.auto_increment_offset=1/*!*/;
/*!\C utf8 *//*!*/;
SET @@session.character_set_client=33,@@session.collation_connection=33,@@session.collation_server=8/*!*/;
SET @@session.lc_time_names=0/*!*/;
SET @@session.collation_database=DEFAULT/*!*/;
BEGIN
/*!*/;
# at 520
# at 671
#170329  5:21:33 server id 1  end_log_pos 702 CRC32 0xb69b0f7d  Xid = 32
COMMIT/*!*/;
# at 702
#170329  6:27:12 server id 1  end_log_pos 805 CRC32 0x491529ff  Query   thread_id=1     exec_time=0     error_code=0
use `mysql`/*!*/;
SET TIMESTAMP=1490740032/*!*/;
create table mytest(id int)
/*!*/;
DELIMITER ;
...后面固定部分省略... 
```

可以看到，除了指定的 mysql 数据库的信息输出了，还非常简化的输出了其他数据库的信息。

mysqlbinlog 最有用的两个选项就是指定时间和位置来输出日志。

指定时间时，将输出指定时间范围内的日志。指定的时间可以不和日志中记录的日志相同。

```sql
[[email protected] data]# mysqlbinlog mysql-bin.000001 --start-datetime='2017-03-28 00:00:01' --stop-datetime='2017-03-29 05:21:23'
...前面固定部分省略...
'/*!*/;
# at 120
#170329  5:20:00 server id 1  end_log_pos 305 CRC32 0xbac43912  Query   thread_id=1     exec_time=0     error_code=0
use `test`/*!*/;
SET TIMESTAMP=1490736000/*!*/;
SET @@session.pseudo_thread_id=1/*!*/;
SET @@session.foreign_key_checks=1, @@session.sql_auto_is_null=0, @@session.unique_checks=1, @@session.autocommit=1/*!*/;
SET @@session.sql_mode=1075838976/*!*/;
SET @@session.auto_increment_increment=1, @@session.auto_increment_offset=1/*!*/;
/*!\C utf8 *//*!*/;
SET @@session.character_set_client=33,@@session.collation_connection=33,@@session.collation_server=8/*!*/;
SET @@session.lc_time_names=0/*!*/;
SET @@session.collation_database=DEFAULT/*!*/;
create table student(studentid int not null primary key,name varchar(30) not null,gender enum('female','mail'))
/*!*/;
# at 305
#170329  5:21:21 server id 1  end_log_pos 441 CRC32 0xde67f702  Query   thread_id=1     exec_time=0     error_code=0
SET TIMESTAMP=1490736081/*!*/;
alter table student change gender gender enum('female','male')
/*!*/;
DELIMITER ;
...后面固定部分省略...
```

同理指定位置也一样，但是指定位置时有个要求是如果指定起始位置，则必须指定日志文件中明确的起始位置。例如，日志文件中有位置 120、305、441，可以指定起始和结束位置为 120、500，但是不可以指定起止位置为 150、500，因为日志文件中不存在 150 这个位置。

```cpp
[[email protected] data]# mysqlbinlog mysql-bin.000001 --start-position=150 --stop-position=441
...前面固定部分省略...
'/*!*/;
ERROR: Error in Log_event::read_log_event(): 'read error', data_len: 4202496, event_type: 0
...后面固定部分省略... 
[[email protected] data]# mysqlbinlog mysql-bin.000001 --start-position=305 --stop-position=500
...前面固定部分省略... 
'/*!*/;
# at 305
#170329  5:21:21 server id 1  end_log_pos 441 CRC32 0xde67f702  Query   thread_id=1     exec_time=0     error_code=0
use `test`/*!*/;
SET TIMESTAMP=1490736081/*!*/;
SET @@session.pseudo_thread_id=1/*!*/;
SET @@session.foreign_key_checks=1, @@session.sql_auto_is_null=0, @@session.unique_checks=1, @@session.autocommit=1/*!*/;
SET @@session.sql_mode=1075838976/*!*/;
SET @@session.auto_increment_increment=1, @@session.auto_increment_offset=1/*!*/;
/*!\C utf8 *//*!*/;
SET @@session.character_set_client=33,@@session.collation_connection=33,@@session.collation_server=8/*!*/;
SET @@session.lc_time_names=0/*!*/;
SET @@session.collation_database=DEFAULT/*!*/;
alter table student change gender gender enum('female','male')
/*!*/;
# at 441
#170329  5:21:33 server id 1  end_log_pos 520 CRC32 0x05a9c5a1  Query   thread_id=1     exec_time=0     error_code=0
SET TIMESTAMP=1490736093/*!*/;
BEGIN
/*!*/;
DELIMITER ;
...后面固定部分省略...
```

### 5.2.2 show binary logs

该语句用于查看当前使用了哪些二进制日志文件。

可以通过查看二进制的 index 文件来查看当前正在使用哪些二进制日志。

```plaintext
[[email protected] data]# cat mysql-bin.index 
./mysql-bin.000003
./mysql-bin.000004
./mysql-bin.000005
./mysql-bin.000006
```

也可以在 mysql 环境中使用 show {binary | master} logs 来查看。binary 和 master 是同义词。

```plaintext
mysql> show binary logs;
+------------------+-----------+
| Log_name         | File_size |
+------------------+-----------+
| mysql-bin.000003 |       167 |
| mysql-bin.000004 |       785 |
| mysql-bin.000005 |      1153 |
| mysql-bin.000006 |       602 |
+------------------+-----------
```

### 5.2.3 show binlog events

**该语句用于查看日志中进行了哪些操作。**

```plaintext
mysql> show binlog events in 'mysql-bin.000005';
```

![img](../assets/733013-20180507091129596-1182363918.png)

可以指定起始位置。同样，起始位置必须指定正确，不能指定不存在的位置。

```python
mysql> show binlog events in 'mysql-bin.000005' from 961;
+------------------+------+------------+-----------+-------------+--------------------------------+
| Log_name         | Pos  | Event_type | Server_id | End_log_pos | Info                           |
+------------------+------+------------+-----------+-------------+--------------------------------+
| mysql-bin.000005 |  961 | Table_map  |         1 |        1019 | table_id: 98 (test.student)    |
| mysql-bin.000005 | 1019 | Write_rows |         1 |        1075 | table_id: 98 flags: STMT_END_F |
| mysql-bin.000005 | 1075 | Xid        |         1 |        1106 | COMMIT /* xid=129 */           |
| mysql-bin.000005 | 1106 | Rotate     |         1 |        1153 | mysql-bin.000006;pos=4         |
+------------------+------+------------+-----------+-------------+--------------------------------+ 
```

### 5.2.4 show master status

该语句用于显示主服务器中的二进制日志信息。如果是主从结构，它只会显示主从结构中主服务器的二进制日志信息。

```plaintext
mysql> show master status;    
+------------------+----------+--------------+------------------+-------------------+
| File             | Position | Binlog_Do_DB | Binlog_Ignore_DB | Executed_Gtid_Set |
+------------------+----------+--------------+------------------+-------------------+
| mysql-bin.000006 |      602 |              |                  |                   |
+------------------+----------+--------------+------------------+-------------------+
```

可以查看到当前正在使用的日志及下一事件记录的开始位置，还能查看到哪些数据库需要记录二进制日志，哪些数据库不记录二进制日志。

## 5.3 删除二进制日志

删除二进制日志有几种方法。不管哪种方法，都会将删除后的信息同步到二进制 index 文件中。

**1.reset master**  **将会删除所有日志，并让日志文件重新从 000001**  **开始。**

```plaintext
mysql> reset master;
```

**2.PURGE { BINARY | MASTER } LOGS { TO 'log_name' | BEFORE datetime_expr }** purge master logs to "binlog_name.00000X" 将会清空 00000X 之前的所有日志文件。例如删除 000006 之前的日志文件。

```plaintext
mysql> purge master logs to "mysql-bin.000006";
mysql> purge binary logs to "mysql-bin.000006";
```

master 和 binary 是同义词
purge master logs before 'yyyy-mm-dd hh:mi:ss' 将会删除指定日期之前的所有日志。但是若指定的时间处在正在使用中的日志文件中，将无法进行 purge。

```plaintext
mysql> purge master logs before '2017-03-29 07:36:40';
mysql> show warnings;
+---------+------+---------------------------------------------------------------------------+
| Level   | Code | Message                                                                   |
+---------+------+---------------------------------------------------------------------------+
| Warning | 1868 | file ./mysql-bin.000003 was not purged because it is the active log file. |
+---------+------+---------------------------------------------------------------------------+
```

**3.**  **使用--expire_logs_days=N**  **选项指定过了多少天日志自动过期清空。** 5.4 二进制日志的记录格式
--------------

在 MySQL 5.1 之前，MySQL 只有一种基于语句 statement 形式的日志记录格式。即将所有的相关操作记录为 SQL 语句形式。但是这样的记录方式对某些特殊信息无法同步记录，例如 uuid，now()等这样动态变化的值。
从 MySQL 5.1 开始，MySQL 支持 statement、row、mixed 三种形式的记录方式。row 形式是基于行来记录，也就是将相关行的每一列的值都在日志中保存下来，这样的结果会导致日志文件变得非常大，但是保证了动态值的确定性。还有一种 mixed 形式，表示如何记录日志由 MySQL 自己来决定。
日志的记录格式由变量 binlog_format 来指定。其值有：row,statement,mixed。innodb 引擎的创始人之一在博客上推荐使用 row 格式。
下面将记录格式改为 row。

```sql
mysql> alter table student add birthday datetime default  now();
mysql> flush logs;
mysql> set binlog_format='row';
mysql> insert into student values(7,'xiaowoniu','female',now());
```

查看产生的日志。

```plaintext
[[email protected] data]# mysqlbinlog mysql-bin.000005
...前面固定部分省略...
'/*!*/;

# at 120

# 170329  8:06:24 server id 1  end_log_pos 200 CRC32 0x0ac02649  Query   thread_id=1     exec_time=0     error_code=0

SET TIMESTAMP=1490745984/*!*/;
SET @@session.pseudo_thread_id=1/*!*/;
SET @@session.foreign_key_checks=1, @@session.sql_auto_is_null=0, @@session.unique_checks=1, @@session.autocommit=1/*!*/;
SET @@session.sql_mode=1075838976/*!*/;
SET @@session.auto_increment_increment=1, @@session.auto_increment_offset=1/*!*/;
/*!\\C utf8 *//*!*/;
SET @@session.character_set_client=33,@@session.collation_connection=33,@@session.collation_server=8/*!*/;
SET @@session.time_zone='SYSTEM'/*!*/;
SET @@session.lc_time_names=0/*!*/;
SET @@session.collation_database=DEFAULT/*!*/;
BEGIN
/*!*/;

# at 200

# 170329  8:06:24 server id 1  end_log_pos 258 CRC32 0xb8cdfd09  Table_map: `test`.`student` mapped to number 94

# at 258

# 170329  8:06:24 server id 1  end_log_pos 314 CRC32 0x8ce6f72c  Write_rows: table id 94 flags: STMT_END_F

BINLOG '
gPraWBMBAAAAOgAAAAIBAAAAAF4AAAAAAAEABHRlc3QAB3N0dWRlbnQABAMP/hIFHgD3AQAMCf3N
uA==
gPraWB4BAAAAOAAAADoBAAAAAF4AAAAAAAEAAgAE//AHAAAACXhpYW93b25pdQGZnDqBmCz35ow=
'/*!*/;

# at 314

# 170329  8:06:24 server id 1  end_log_pos 345 CRC32 0x7a48c057  Xid = 114

COMMIT/*!*/;
DELIMITER ;
...后面固定部分省略...
```

发现是一堆看不懂的东西，使用-vv 可将这些显示出来。可以看出，结果中记录的非常详细，这也是为什么基于 row 记录日志会导致日志文件极速变大。

```sql
[[email protected] data]# mysqlbinlog mysql-bin.000005 -vv
...前面省略...
BINLOG '
gPraWBMBAAAAOgAAAAIBAAAAAF4AAAAAAAEABHRlc3QAB3N0dWRlbnQABAMP/hIFHgD3AQAMCf3N
uA==
gPraWB4BAAAAOAAAADoBAAAAAF4AAAAAAAEAAgAE//AHAAAACXhpYW93b25pdQGZnDqBmCz35ow=
'/*!*/;

### INSERT INTO `test`.`student`

### SET

### @1=7 /*INT meta=0 nullable=0 is_null=0*/

### @2='xiaowoniu' /*VARSTRING(30) meta=30 nullable=0 is_null=0*/

### @3=1 /*ENUM(1 byte) meta=63233 nullable=1 is_null=0*/

### @4='2017-03-29 08:06:24' /*DATETIME(0) meta=0 nullable=1 is_null=0*/

# at 314

...后面省略...
```

还有一种 mixed 模式。这种模式下默认会采用 statement 的方式记录，只有以下几种情况会采用 row 的形式来记录日志。 1.表的存储引擎为 NDB，这时对表的 DML 操作都会以 row 的格式记录。 2.使用了 uuid()、user()、current_user()、found_rows()、row_count()等不确定函数。但测试发现对 now()函数仍会以 statement 格式记录，而 sysdate()函数会以 row 格式记录。 3.使用了 insert delay 语句。 4.使用了临时表。

## 5.5 二进制日志相关的变量

注意：在配置 binlog 相关变量的时候，相关变量名总是搞混，因为有的是 binlog，有的是 log_bin，当他们分开的时候，log 在前，当它们一起的时候，bin 在前。在配置文件中也同样如此。

- log_bin = {on | off | base_name} #指定是否启用记录二进制日志或者指定一个日志路径(路径不能加.否则.后的被忽略)
- sql_log_bin ={ on | off } #指定是否启用记录二进制日志，只有在 log_bin 开启的时候才有效
- expire_logs_days = #指定自动删除二进制日志的时间，即日志过期时间
- binlog_do_db = #明确指定要记录日志的数据库
- binlog_ignore_db = #指定不记录二进制日志的数据库
- log_bin_index = #指定 mysql-bin.index 文件的路径
- binlog_format = { mixed | row | statement } #指定二进制日志基于什么模式记录
- binlog_rows_query_log_events = { 1|0 } # MySQL5.6.2 添加了该变量，当 binlog format 为 row 时，默认不会记录 row 对应的 SQL 语句，设置为 1 或其他 true 布尔值时会记录，但需要使用 mysqlbinlog -v 查看，这些语句是被注释的，恢复时不会被执行。
- max_binlog_size = #指定二进制日志文件最大值，超出指定值将自动滚动。但由于事务不会跨文件，所以并不一定总是精确。
- binlog_cache_size = 32768 # **基于事务类型的日志会先记录在缓冲区**，当达到该缓冲大小时这些日志会写入磁盘
- max_binlog_cache_size = #指定二进制日志缓存最大大小，硬限制。默认 4G，够大了，建议不要改
- binlog_cache_use：使用缓存写二进制日志的次数(这是一个实时变化的统计值)
- binlog_cache_disk_use:使用临时文件写二进制日志的次数，当日志超过了 binlog_cache_size 的时候会使用临时文件写日志，如果该变量值不为 0，则考虑增大 binlog_cache_size 的值
- binlog_stmt_cache_size = 32768 #一般等同于且决定 binlog_cache_size 大小，所以修改缓存大小时只需修改这个而不用修改 binlog_cache_size
- binlog_stmt_cache_use：使用缓存写二进制日志的次数
- binlog_stmt_cache_disk_use: 使用临时文件写二进制日志的次数，当日志超过了 binlog_cache_size 的时候会使用临时文件写日志，如果该变量值不为 0，则考虑增大 binlog_cache_size 的值
- sync_binlog = { 0 | n } #这个参数直接影响 mysql 的性能和完整性
  - sync_binlog=0:不同步，日志何时刷到磁盘由 FileSystem 决定，这个性能最好。
  - sync_binlog=n:每写 n 次事务(注意，对于非事务表来说，是 n 次事件，对于事务表来说，是 n 次事务，而一个事务里可能包含多个二进制事件)，MySQL 将执行一次磁盘同步指令 fdatasync()将缓存日志刷新到磁盘日志文件中。Mysql 中默认的设置是 sync_binlog=0，即不同步，这时性能最好，但风险最大。一旦系统奔溃，缓存中的日志都会丢失。**在 innodb 的主从复制结构中，如果启用了二进制日志(几乎都会启用)，要保证事务的一致性和持久性的时候，必须将 sync_binlog 的值设置为 1，因为每次事务提交都会写入二进制日志，设置为 1 就保证了每次事务提交时二进制日志都会写入到磁盘中，从而立即被从服务器复制过去。** 5.6 二进制日志定点还原数据库

----------------
只需指定二进制日志的起始位置（可指定终止位置）并将其保存到 sql 文件中，由 mysql 命令来载入恢复即可。当然直接通过管道送给 mysql 命令也可。
至于是基于位置来恢复还是基于时间点来恢复，这两种行为都可以。选择时间点来恢复比较直观些，并且跨日志文件恢复时更方便。

```plaintext
mysqlbinlog --stop-datetime="2014-7-2 15:27:48" /tmp/mysql-bin.000008 | mysql -u user -p password
```

恢复多个二进制日志文件时：

```plaintext
mysqlbinlog mysql-bin.[\*] | mysql -uroot -p password
```

或者将它们导入到一个文件中后恢复。

```plaintext
mysqlbinlog mysql-bin.000001 > /tmp/a.sql
mysqlbinlog mysql-bin.000002 >>/tmp/a.sql
mysql -u root -p password -e "source /tmp/a.sql"
```

```
