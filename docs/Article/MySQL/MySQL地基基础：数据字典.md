# MySQL 地基基础：数据字典

### 数据字典是什么

MySQL 数据字典的发展史：

- MySQL 4 提供了 information_schema 数据字典，可以简单的使用 SQL 来检索系统元数据。
- MySQL 5.5 提供了 performa nce_schema 性能引擎，可以查看 MySQL 性能问题，但是这个有一定难度。
- MySQL 5.7 提供了 sys 系统数据库，其包含的表、视图、函数、存储过程、触发器可以帮我们快速了解数据库的情况。

**数据字典的作用**

数据字典我们用一句话来概括，就是数据的数据，用于查询数据库中数据的信息内容。

### MySQL information_schema 详解（崭露头角)

我们部署完 MySQL 后发现会自动生成一个 information_schema 库，这个库提供了访问 MySQL 元数据的访问方式。

那么什么是元数据呢？元数据就是数据字典，就是数据的数据，前者这个数据就是我们所知道，所用的数据，后者这个数据就是解释前者的数据。比如，数据库名、表名、列名、列类型、权限等等。

这个库中存在这大量的视图，我们只能查看其视图内容，不能修改。

我们看看这个库中到底有什么内容。

```sql
mysql> use sys
mysql> select * from schema_object_overview where db='information_schema';
+--------------------+-------------+-------+
| db                 | object_type | count |
+--------------------+-------------+-------+
| information_schema | SYSTEM VIEW |    61 |
+--------------------+-------------+-------+
1 row in set (0.10 sec)
```

结果显示，有 61 张系统视图。既然是视图，那就没有相关的数据文件了，我们去验证一下。

到 MySQL 的 data 目录中看看是否有 information_schema 相关的数据文件。经过查询根本找不到这个库的目录。

都有什么视图内容呢？我们可以通过 show tables 命令查看。

```plaintext
mysql> use information_schema
mysql> show tables;
```

接下来我们讲几个 information_schema 中重要常用视图。

- **SCHEMATA** ：查看 MySQL 实例中所有数据库信息
- **TABLES** ：查询数据库中的表、视图信息
- **COLUMNS** ：查询表中的列信息
- **STATISTICS** ：查询表中的索引信息
- **USER_PRIVILEGES** ：查询用户权限信息
- **SCHEMA_PRIVILEGES** ：查询数据库权限信息
- **TABLE_PRIVILEGES** ：查询表权限信息
- **COLUMN_PRIVILEGES** ：查询列权限信息
- **CHARACTER_SETS** ：查询字符集信息

好了，information_schema 不做过多的介绍了，查询的内容比较全面，也比较简单，大家可以自行去探索。

### MySQL performance_schema 详解（成长升级）

MySQL 在 5.7 开始，对数据字典的使用有了很大的改进，使用上更加的方便，提供的能力也更高。它可以查询事务信息、获取元数据锁、跟踪事件、统计内存使用情况等等。

我们先说一个你想不到的事情，MySQL 的 performance_schema 其实是一个引擎。

```sql
mysql> select * from information_schema.engines;
+--------------------+---------+----------------------------------------------------------------+--------------+------+------------+
| ENGINE             | SUPPORT | COMMENT                                                        | TRANSACTIONS | XA   | SAVEPOINTS |
+--------------------+---------+----------------------------------------------------------------+--------------+------+------------+
| CSV                | YES     | CSV storage engine                                             | NO           | NO   | NO         |
| MRG_MYISAM         | YES     | Collection of identical MyISAM tables                          | NO           | NO   | NO         |
| MyISAM             | YES     | MyISAM storage engine                                          | NO           | NO   | NO         |
| BLACKHOLE          | YES     | /dev/null storage engine (anything you write to it disappears) | NO           | NO   | NO         |
| InnoDB             | DEFAULT | Supports transactions, row-level locking, and foreign keys     | YES          | YES  | YES        |
| PERFORMANCE_SCHEMA | YES     | Performance Schema                                             | NO           | NO   | NO         |
| ARCHIVE            | YES     | Archive storage engine                                         | NO           | NO   | NO         |
| MEMORY             | YES     | Hash based, stored in memory, useful for temporary tables      | NO           | NO   | NO         |
| FEDERATED          | NO      | Federated MySQL storage engine                                 | NULL         | NULL | NULL       |
+--------------------+---------+----------------------------------------------------------------+--------------+------+------------+
9 rows in set (0.00 sec)
```

看到了吗，在 MySQL 支持的存储引擎中发现了 PERFORMANCE_SCHEMA，是不是很神奇。

在 MySQL 配置中可以配置启用这个引擎，默认是启动的。

在 my.cnf 中配置如下：

```plaintext
[mysqld]  
performance_schema=ON
```

验证一下参数是否启动：

```plaintext
mysql> show variables like 'performance_schema';
+--------------------+-------+
| Variable_name      | Value |
+--------------------+-------+
| performance_schema | ON    |
+--------------------+-------+
1 row in set (0.01 sec)
```

虽然它是一个引擎，但是我们可以像使用数据库那样使用 use 来使用它。这个库里到底有什么内容呢？

```sql
mysql> use sys;
mysql> select * from schema_object_overview where db='performance_schema';
+--------------------+-------------+-------+
| db                 | object_type | count |
+--------------------+-------------+-------+
| performance_schema | BASE TABLE  |    87 |
+--------------------+-------------+-------+
1 row in set (0.06 sec)
```

结果显示，有 87 张表。我们知道 MySQL 有很多需要监控和统计的内容，而 performance_schema 将这些监控、统计信息之类的内容通过库中的表统计出来，都展现在这些表中。那么这些表都是做什么用的呢？我们就去研究一下。

总体分类：

- setup 表
- instance 表
- wait event 表
- stage event 表
- statement event 表
- transaction event 表
- summary 表
- other 表

#### setup 表

```plaintext
mysql> use performance_schema
mysql> show tables like '%setup%';
+----------------------------------------+
| Tables_in_performance_schema (%setup%) |
+----------------------------------------+
| setup_actors                           |
| setup_consumers                        |
| setup_instruments                      |
| setup_objects                          |
| setup_timers                           |
+----------------------------------------+
5 rows in set (0.00 sec)
```

**setup_actors**

作用：配置用户维度的监控，默认监控所有用户。

```sql
mysql> select * from setup_actors;
+------+------+------+---------+---------+
| HOST | USER | ROLE | ENABLED | HISTORY |
+------+------+------+---------+---------+
| %    | %    | %    | YES     | YES     |
+------+------+------+---------+---------+
1 row in set (0.00 sec)
```

`%` 表示默认是对所有的用户监控。

**setup_consumers**

作用：配置事件的消费者类型，管理将收集的监控内容保存在哪些表中。

```sql
mysql> select * from setup_consumers;
+----------------------------------+---------+
| NAME                             | ENABLED |
+----------------------------------+---------+
| events_stages_current            | NO      |
| events_stages_history            | NO      |
| events_stages_history_long       | NO      |
| events_statements_current        | YES     |
| events_statements_history        | YES     |
| events_statements_history_long   | NO      |
| events_transactions_current      | NO      |
| events_transactions_history      | NO      |
| events_transactions_history_long | NO      |
| events_waits_current             | NO      |
| events_waits_history             | NO      |
| events_waits_history_long        | NO      |
| global_instrumentation           | YES     |
| thread_instrumentation           | YES     |
| statements_digest                | YES     |
+----------------------------------+---------+
15 rows in set (0.00 sec)
```

有 15 条记录，这些配置呢存在着上下级关系，原则是当上级监控生效，下级监控才起作用。上下级对应关系如下：

```global_instrumentation
|----thread_instrumentation
|         |----events_waits_current
|         |           |----events_waits_history
|         |           |----events_waits_history_long
|         |----events_stages_current
|         |           |----events_stages_history
|         |           |----events_stages_history_long
|         |----events_statements_current
|                     |----events_statements_history
|                     |----events_statements_history_long
|-----statements_digest
```

- 第一级：global_instrumentation 是全局统计，只有它生效其余的才生效。如果设置它生效，其余都设置未生效，则只收集全局统计信息，不收集用户级统计信息。
- 第二级：thread_instrumentation 是用户线程统计，statements_digest 是全局 SQL 统计。
- 第三级：events_waits_current、events_stages_current、events_statements_current，分别是事件的 wait、stage、statement 的统计。
- 第四级：分别是对应的历史统计内容了。

**setup_instruments**

作用：配置仪器，这个表中内容非常丰富，包含了统计 SQL 执行阶段情况、统计等待事件情况、IO 情况、内存情况、锁情况等。

配置内容很多，我们分组看一下几大类。

```cpp
mysql> select name,count(*) from setup_instruments group by LEFT(name,5);
+-------------------------------------------+----------+
| name                                      | count(*) |
+-------------------------------------------+----------+
| idle                                      |        1 |
| memory/performance_schema/mutex_instances |      377 |
| stage/sql/After create                    |      129 |
| statement/sql/select                      |      193 |
| transaction                               |        1 |
| wait/synch/mutex/sql/TC_LOG_MMAP::LOCK_tc |      319 |
+-------------------------------------------+----------+
6 rows in set (0.00 sec)
```

如果你执行上面的这个分组报错如下：

```javascript
ERROR 1055 (42000): Expression #1 of SELECT list is not in GROUP BY clause and contains nonaggregated column 'performance_schema.setup_instruments.NAME' which is not functionally dependent on columns in GROUP BY clause; this is incompatible with sql_mode=only_full_group_by
```

解决方法：这是由于 `sql_mode=only_full_group_by` 导致。

```sql
mysql> SELECT @@SESSION.sql_mode;
+-------------------------------------------------------------------------------------------------------------------------------------------+
| @@SESSION.sql_mode                                                                                                                        |
+-------------------------------------------------------------------------------------------------------------------------------------------+
| ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION |
+-------------------------------------------------------------------------------------------------------------------------------------------+
1 row in set (0.00 sec)
mysql> set @@session.sql_mode ='STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION';
```

通过修改会话级的 sql_mode 可以解决问题。

- idle：表示空闲
- memory：表示内存的统计
- stage：表示 SQL 语句每个阶段的统计
- statement：表示 SQL 语句的统计
- transaction：表示事务的统计
- wait：表示各种等待的统计

**setup_objects**

作用：配置监控对象。

```sql
mysql> select * from setup_objects;
+-------------+--------------------+-------------+---------+-------+
| OBJECT_TYPE | OBJECT_SCHEMA      | OBJECT_NAME | ENABLED | TIMED |
+-------------+--------------------+-------------+---------+-------+
| EVENT       | mysql              | %           | NO      | NO    |
| EVENT       | performance_schema | %           | NO      | NO    |
| EVENT       | information_schema | %           | NO      | NO    |
| EVENT       | %                  | %           | YES     | YES   |
| FUNCTION    | mysql              | %           | NO      | NO    |
| FUNCTION    | performance_schema | %           | NO      | NO    |
| FUNCTION    | information_schema | %           | NO      | NO    |
| FUNCTION    | %                  | %           | YES     | YES   |
| PROCEDURE   | mysql              | %           | NO      | NO    |
| PROCEDURE   | performance_schema | %           | NO      | NO    |
| PROCEDURE   | information_schema | %           | NO      | NO    |
| PROCEDURE   | %                  | %           | YES     | YES   |
| TABLE       | mysql              | %           | NO      | NO    |
| TABLE       | performance_schema | %           | NO      | NO    |
| TABLE       | information_schema | %           | NO      | NO    |
| TABLE       | %                  | %           | YES     | YES   |
| TRIGGER     | mysql              | %           | NO      | NO    |
| TRIGGER     | performance_schema | %           | NO      | NO    |
| TRIGGER     | information_schema | %           | NO      | NO    |
| TRIGGER     | %                  | %           | YES     | YES   |
+-------------+--------------------+-------------+---------+-------+
20 rows in set (0.00 sec)
```

通过结果我们看到默认对 EVENT、FUNCTION、PROCEDURE、TABLE、TRIGGER 的配置：

- mysql 库都不监控
- performance_schema 都不监控
- information_schema 都不监控
- 其余库都监控

**setup_timers**

作用：配置每种类型统计的时间单位。

```sql
mysql> select * from setup_timers;
+-------------+-------------+
| NAME        | TIMER_NAME  |
+-------------+-------------+
| idle        | MICROSECOND |
| wait        | CYCLE       |
| stage       | NANOSECOND  |
| statement   | NANOSECOND  |
| transaction | NANOSECOND  |
+-------------+-------------+
5 rows in set (0.00 sec)
```

- idle：微妙
- wait：CPU 时钟
- stage：纳秒
- statement：纳秒
- transaction：纳秒

那么为什么使用这样的时间呢，这个时间定义来源于 MySQL 的基础定义。

```sql
mysql> select * from performance_timers;
+-------------+-----------------+------------------+----------------+
| TIMER_NAME  | TIMER_FREQUENCY | TIMER_RESOLUTION | TIMER_OVERHEAD |
+-------------+-----------------+------------------+----------------+
| CYCLE       |      2193855721 |                1 |             18 |
| NANOSECOND  |      1000000000 |                1 |            152 |
| MICROSECOND |         1000000 |                1 |            155 |
| MILLISECOND |            1037 |                1 |            155 |
| TICK        |             108 |                1 |            561 |
+-------------+-----------------+------------------+----------------+
5 rows in set (0.00 sec)
```

TICK：是系统的相对时间单位，也称为系统的时基，来源于定时器的周期性中断。

#### instance 表

```plaintext
mysql> use performance_schema
mysql> show tables like '%instances';
+-------------------------------------------+
| Tables_in_performance_schema (%instances) |
+-------------------------------------------+
| cond_instances                            |
| file_instances                            |
| mutex_instances                           |
| prepared_statements_instances             |
| rwlock_instances                          |
| socket_instances                          |
+-------------------------------------------+
6 rows in set (0.00 sec)
```

- **cond_instances** ：保存系统中使用的条件变量的对象
- **file_instances** ：保存系统中打开文件的对象
- **mutex_instances** ：保存系统中使用互斥变量的对象
- **prepared_statements_instances** ：保存预处理 SQL 语句的 statements 的对象
- **rwlock_instances** ：保存系统中使用读写锁的对象
- **socket_instances** ：保存系统中使用的 socket 的对象

#### wait event 表

```plaintext
mysql> use performance_schema
mysql> show tables like '%waits%';
+-----------------------------------------------+
| Tables_in_performance_schema (%waits%)        |
+-----------------------------------------------+
| events_waits_current                          |
| events_waits_history                          |
| events_waits_history_long                     |
| events_waits_summary_by_account_by_event_name |
| events_waits_summary_by_host_by_event_name    |
| events_waits_summary_by_instance              |
| events_waits_summary_by_thread_by_event_name  |
| events_waits_summary_by_user_by_event_name    |
| events_waits_summary_global_by_event_name     |
| table_io_waits_summary_by_index_usage         |
| table_io_waits_summary_by_table               |
| table_lock_waits_summary_by_table             |
+-----------------------------------------------+
12 rows in set (0.00 sec)
```

这里是说前三个，其他的后面介绍。

- **events_waits_current** ：保存当前线程的等待事件
- **events_waits_history** ：保存每个线程的最近 N 个等待事件
- **events_waits_history_long** ：保存所有线程的最近 N 个等待事件

#### stage event 表

```plaintext
mysql> use performance_schema
mysql> show tables like '%stage%';
+------------------------------------------------+
| Tables_in_performance_schema (%stage%)         |
+------------------------------------------------+
| events_stages_current                          |
| events_stages_history                          |
| events_stages_history_long                     |
| events_stages_summary_by_account_by_event_name |
| events_stages_summary_by_host_by_event_name    |
| events_stages_summary_by_thread_by_event_name  |
| events_stages_summary_by_user_by_event_name    |
| events_stages_summary_global_by_event_name     |
+------------------------------------------------+
8 rows in set (0.00 sec)
```

这里是说前三个，其他的后面介绍。

- **events_stages_current** ：保存当前线程所处的执行阶段
- **events_stages_history** ：保存当前线程最新的 N 个执行阶段
- **events_stages_history_long** ：保存当前线程最新的 N 个执行阶段

#### statement event 表

```plaintext
mysql> use performance_schema
mysql> show tables like '%statement%';
+----------------------------------------------------+
| Tables_in_performance_schema (%statement%)         |
+----------------------------------------------------+
| events_statements_current                          |
| events_statements_history                          |
| events_statements_history_long                     |
| events_statements_summary_by_account_by_event_name |
| events_statements_summary_by_digest                |
| events_statements_summary_by_host_by_event_name    |
| events_statements_summary_by_program               |
| events_statements_summary_by_thread_by_event_name  |
| events_statements_summary_by_user_by_event_name    |
| events_statements_summary_global_by_event_name     |
| prepared_statements_instances                      |
+----------------------------------------------------+
11 rows in set (0.00 sec)
```

这里是说前三个，其他的后面介绍。

- **events_statements_current** ：保存当前线程执行的语句
- **events_statements_history** ：保存每个线程最新的 N 个执行的语句
- **events_statements_history_long** ：保存每个线程最新的 N 个执行的语句

#### transaction event 表

```plaintext
mysql> use performance_schema
mysql> show tables like '%transactions%';
+------------------------------------------------------+
| Tables_in_performance_schema (%transactions%)        |
+------------------------------------------------------+
| events_transactions_current                          |
| events_transactions_history                          |
| events_transactions_history_long                     |
| events_transactions_summary_by_account_by_event_name |
| events_transactions_summary_by_host_by_event_name    |
| events_transactions_summary_by_thread_by_event_name  |
| events_transactions_summary_by_user_by_event_name    |
| events_transactions_summary_global_by_event_name     |
+------------------------------------------------------+
8 rows in set (0.00 sec)
```

这里是说前三个，其他的后面介绍。

- **events_transactions_current** ：保存每个线程当前事务事件
- **events_transactions_history** ：保存每个线程最近的 N 个事务事件
- **events_transactions_history_long** ：保存每个线程最近的 N 个事务事件

#### summary 表

```plaintext
mysql> use performance_schema
mysql> show tables like '%summary%';
+------------------------------------------------------+
| Tables_in_performance_schema (%summary%)             |
+------------------------------------------------------+
| events_stages_summary_by_account_by_event_name       |
| events_stages_summary_by_host_by_event_name          |
| events_stages_summary_by_thread_by_event_name        |
| events_stages_summary_by_user_by_event_name          |
| events_stages_summary_global_by_event_name           |
| events_statements_summary_by_account_by_event_name   |
| events_statements_summary_by_digest                  |
| events_statements_summary_by_host_by_event_name      |
| events_statements_summary_by_program                 |
| events_statements_summary_by_thread_by_event_name    |
| events_statements_summary_by_user_by_event_name      |
| events_statements_summary_global_by_event_name       |
| events_transactions_summary_by_account_by_event_name |
| events_transactions_summary_by_host_by_event_name    |
| events_transactions_summary_by_thread_by_event_name  |
| events_transactions_summary_by_user_by_event_name    |
| events_transactions_summary_global_by_event_name     |
| events_waits_summary_by_account_by_event_name        |
| events_waits_summary_by_host_by_event_name           |
| events_waits_summary_by_instance                     |
| events_waits_summary_by_thread_by_event_name         |
| events_waits_summary_by_user_by_event_name           |
| events_waits_summary_global_by_event_name            |
| file_summary_by_event_name                           |
| file_summary_by_instance                             |
| memory_summary_by_account_by_event_name              |
| memory_summary_by_host_by_event_name                 |
| memory_summary_by_thread_by_event_name               |
| memory_summary_by_user_by_event_name                 |
| memory_summary_global_by_event_name                  |
| objects_summary_global_by_type                       |
| socket_summary_by_event_name                         |
| socket_summary_by_instance                           |
| table_io_waits_summary_by_index_usage                |
| table_io_waits_summary_by_table                      |
| table_lock_waits_summary_by_table                    |
+------------------------------------------------------+
36 rows in set (0.00 sec)
```

这些 summary 表有很多，提供了一段时间内已经执行完成的事件的汇总情况，我们从不同的维度整理如下：

- 按阶段事件的汇总摘要：events_stages_summary\_\*
- 按语句事件的汇总摘要：events_statements_summary\_\*
- 按事务事件的汇总摘要：events_transactions_summary\_\*
- 按等待事件的汇总摘要：events_waits_summary\_\*
- 按文件事件的汇总摘要：file_summary\_\*
- 按内存事件的汇总摘要：memory_summary\_\*
- 按对象事件的汇总摘要：objects_summary_global_by_type
- 按套接字事件的汇总摘要：socket_summary\_\*
- 按表事件的汇总摘要：table_summary\_\*

#### other 表

其他的表还有很多，可以监控统计 accounts、file、status、hosts、memory、metadata_locks、replication、session、socket、table、threads 等。

好了，performance_schema 是数据库，是性能引擎，内部逻辑比较复杂，能做的事情也很多，这里就先介绍到这里，大家可以继续深入研究。

### MySQL sys 详解（演变进化）

MySQL 在 5.7 版本引入了 sys Schema，这个 sys 可以理解为是一个 MySQL 系统库，这个库中提供了表、视图、函数、存储过程、触发器，这些就可以帮我们快捷、高效地知道 MySQL 数据库的元数据信息，比如我们可以了解：SQL 执行情况是否使用了索引，是否走了全表扫描，统计信息的情况、内存使用情况、IO 使用情况、会话连接等等。

前面我们学习了 information_schema 和 performance_schema，这个 sys 提供的视图其实就是前面这两个化繁为简的总结，降低复杂度，让你更快乐的了解 MySQL 的现状。可见 MySQL 在自我优化方面是多么的努力，它帮你做了很多的工作，我们可以更简单的获取更直观的数据，怎么样，MySQL 优秀吧。

说这么多了，这个 sys 库里到底有什么内容呢？好，赶紧一睹芳容。

```sql
mysql> use sys
mysql> select * from schema_object_overview where db='sys';
+-----+---------------+-------+
| db  | object_type   | count |
+-----+---------------+-------+
| sys | FUNCTION      |    22 |
| sys | PROCEDURE     |    26 |
| sys | VIEW          |   100 |
| sys | BASE TABLE    |     1 |
| sys | INDEX (BTREE) |     1 |
| sys | TRIGGER       |     2 |
+-----+---------------+-------+
6 rows in set (0.01 sec)
```

结果显示：

类型

数量

函数

22

存储过程

26

视图

100

表

1

索引

1

触发器

2

这些内容可以帮我们做什么呢？

- 视图：获取更可读的 performance_schema 中的数据
- 存储过程：调整 performance_schema 的配置信息，生成系统诊断报告等
- 函数：查询 performance_schema 配置信息，提供格式化数据等

#### 1 张表

在这些所有内容中，我们常用的就是这一张表和其他视图，我们先来看看这唯一一张表，它是 sys_config。

```sql
mysql> select * from sys_config;
+--------------------------------------+-------+---------------------+--------+
| variable                             | value | set_time            | set_by |
+--------------------------------------+-------+---------------------+--------+
| diagnostics.allow_i_s_tables         | OFF   | 2020-12-16 19:14:32 | NULL   |
| diagnostics.include_raw              | OFF   | 2020-12-16 19:14:32 | NULL   |
| ps_thread_trx_info.max_length        | 65535 | 2020-12-16 19:14:32 | NULL   |
| statement_performance_analyzer.limit | 100   | 2020-12-16 19:14:32 | NULL   |
| statement_performance_analyzer.view  | NULL  | 2020-12-16 19:14:32 | NULL   |
| statement_truncate_len               | 64    | 2020-12-16 19:14:32 | NULL   |
+--------------------------------------+-------+---------------------+--------+
6 rows in set (0.00 sec)
```

只有简单的 6 行数据，这张表保存的是基础参数的配置内容。内容级别是会话级。默认最后一列 set_by（配置修改者）为空，其保存的内容是最后一次修改配置时的用户名。

参数说明

- diagnostics.allow_i_s_tables：默认 OFF，这参数控制调用 diagnostics() 存储过程时会扫描 information_schema.tables 找到所有的基表与 statistics 表关联查询，扫描每个表的统计信息。
- diagnostics.include_raw：默认 OFF，这参数控制调用 diagnostics() 存储过程输出包含 metrics 视图的原始信息。
- ps_thread_trx_info.max_length：默认 65535，保存的是 ps_thread_trx_info() 函数生成的 json 输出内容的最大长度。
- statement_performance_analyzer.limit：默认 100，返回不具有内置限制的视图的行数。
- statement_performance_analyzer.view：默认 NULL，给 statement_performance_analyzer() 存储过程当作入参使用的自定义查询或视图名称。
- statement_truncate_len：默认 64，控制 format_statement() 函数返回的语句的最大长度。

接下来我们测试修改一下 statement_truncate\\len 这个参数内容：

```sql
# statement_truncate_len，调用 format_statement()函数返回是 64 字节长度的值，在未被调用过任何涉及到该配置选项的函数之前，该参数的值是 NULL。
mysql> select @sys.statement_truncate_len;
+----------------------------------------------------------+
| @sys.statement_truncate_len                              |
+----------------------------------------------------------+
| NULL                                                     |
+----------------------------------------------------------+
1 row in set (0.00 sec)
# 调用一下 format_statement()函数
mysql> set @stmt='select variable,value,set_time,set_by from sys_config';
mysql> select format_statement(@stmt);
+----------------------------------------------------------+
| format_statement(@stmt)                                  |
+----------------------------------------------------------+
| select variable,value,set_time,set_by from sys_config |
+----------------------------------------------------------+
1 row in set (0.00 sec)
此时结果可以正常显示 SQL。
# 调用过 format_statement()函数之后，参数的值会更新为 64
mysql> select @sys.statement_truncate_len;
+-----------------------------+
| @sys.statement_truncate_len |
+-----------------------------+
| 64                          |
+-----------------------------+
1 row in set (0.00 sec)
此时看到 statement_truncate_len 值内容为 64 了
#修改一下 statement_truncate_len 的值为 32
mysql> set @sys.statement_truncate_len=32;
mysql> select @sys.statement_truncate_len;
+-----------------------------+
| @sys.statement_truncate_len |
+-----------------------------+
|                          32 |
+-----------------------------+
1 row in set (0.00 sec)
# 再次调用 format_statement()函数，可以看到返回的结果内容显示不全了，因为我们把 statement_truncate_len 改为了 32 导致。
mysql> select format_statement(@stmt);   
+-----------------------------------+
| format_statement(@stmt)           |
+-----------------------------------+
| select variabl ... rom sys_config |
+-----------------------------------+
1 row in set (0.00 sec)
```

上面这 6 行配置时默认自带的，sys_config 中还有一个 sys.debug 参数，这个参数默认没有，我们可以手工插入。

**debug**

默认是 NULL，调用 diagnostics() 和 execute_prepared_stmt() 存储过程，执行检查。这个参数默认不存在，是临时使用的。

```sql
# 会话级设置
set @sys.debug = NULL;
# 所有会话使用，需要插入到表中
mysql> insert into sys_config (variable, value) values('debug', 'ON');
mysql> select * from sys_config;
+--------------------------------------+-------+---------------------+--------+
| variable                             | value | set_time            | set_by |
+--------------------------------------+-------+---------------------+--------+
| debug                                | ON    | 2021-02-07 15:53:12 | NULL   |
| diagnostics.allow_i_s_tables         | OFF   | 2020-12-16 19:14:32 | NULL   |
| diagnostics.include_raw              | OFF   | 2020-12-16 19:14:32 | NULL   |
| ps_thread_trx_info.max_length        | 65535 | 2020-12-16 19:14:32 | NULL   |
| statement_performance_analyzer.limit | 100   | 2020-12-16 19:14:32 | NULL   |
| statement_performance_analyzer.view  | NULL  | 2020-12-16 19:14:32 | NULL   |
| statement_truncate_len               | 64    | 2020-12-16 19:14:32 | NULL   |
+--------------------------------------+-------+---------------------+--------+
7 rows in set (0.00 sec)
# 更新
mysql> update sys_config set value = 'OFF' where variable = 'debug';
```

#### 2 个触发器

前面 sys_config 这个表介绍的差不多了，接下来我们说一下这两个触发器，他们和这张表有紧密的关系。

在 MySQL 5.7 开始提供了一个新的用户 mysql.sys，这个用户可避免修改或删除 root 用户时发生的问题，但是该用户被锁定是无法连接客户端的。

接下来说的两个触发器，在定义时使用了 `[[email protected]](/cdn-cgi/l/email-protection)`，就是说只能用 mysql.sys 调用触发器，从而对表 sys_config 的内容做修改，如果 mysql.sys 用户不存在会报错

```plaintext
ERROR 1449 (HY000): The user specified as a definer ('mysql.sys'@'localhost') does not exist
```

假如，我是说假如 mysql.sys 用户被你给误删除了，或者其他原因导致这个用户不存在了，我们如何补救呢？（建议：千万不要去动这个用户，以免造成不必要的麻烦）

```sql
# 首先创建用户，并赋予使用触发器权限
mysql> grant TRIGGER on sys.* to 'mysql.sys'@'localhost' identified by '123456';
mysql> INSERT INTO sys.sys_config (variable, value) VALUES('debug', 'ON');    
ERROR 1143 (42000): SELECT command denied to user 'mysql.sys'@'localhost' for column 'set_by' in table 'sys_config'
# 还需要赋予 select、insert、update 权限
mysql> grant select,insert,update on sys.sys_config to 'mysql.sys'@'localhost';
mysql> INSERT INTO sys.sys_config (variable, value) VALUES('debug', 'ON'); 
Query OK, 1 row affected (0.02 sec)
mysql> UPDATE sys.sys_config SET value = 'OFF' WHERE variable = 'debug';
Query OK, 1 row affected (0.02 sec)
Rows matched: 1  Changed: 1  Warnings: 0
```

**sysconfiginsertsetuser** 当对 sys.sys_config 表做 insert 操作时，该触发器会将 sys_config 表的 set_by 列设置为当前用户名。 **sysconfigupdatesetuser**

当对 sys.sys_config 表做 insert 操作时，该触发器会将 sys_config 表的 set_by 列设置为当前用户名。

这两个触发器可以更新 set_by 字段都有一个前提条件：

```plaintext
mysql> set @sys.ignore_sys_config_triggers=0;
```

#### 100 张视图

在 MySQL 的 sys 库中有 100 个视图，其中有 52 个是字母的，有 48 个是 x$开头的，有什么区别呢？前者是格式化的数据，更加适合人类阅读；后者是数据库原始数据，适合工具采集数据使用。

我们重点介绍一下字母开头的视图，重点分为几类：

- host_summary：服务器层级，以 IP 分组，汇总 IO 信息。
- innodb：InnoDB 层级，汇总 innodb 存储引擎信息和事务锁、等待等信息。
- io：IO 层级，汇总 IO 使用情况、IO 等待情况等。
- memory：内存使用情况。
- metrics：数据库内部统计值。
- processlist：线程情况。
- ps_check_lost_instrumentation：发生监控丢失的信息情况。
- schema：模式层级，汇总表统计信息等。
- session：会话层级，汇总会话情况。
- statement：执行语句层级，汇总统计信息等。
- user_summary：用户层级，以用户分组，汇总用户使用文件 IO 信息，执行语句的统计信息等。
- wait：汇总主机，等待事情等。

接下来我们重点介绍几个视图。

- **host_summary** ：这个视图我们可以查看连接数据库的主机情况，统计每个主机 SQL 执行次数、SQL 执行时长、表扫描次数、文件 IO 情况、连接情况、用户情况、内存分布情况。通过这些信息我们可以快速了解连接数据库的主机情况。
- **hostsummarybyfileio_type** ：查询连接数据库每个主机的文件 IO 使用情况。
- **hostsummarybyfileio** ：查询连接数据库主机的总 IO 使用情况。
- **innodbbufferstatsbyschema** ：扫描整个 buffer pool 来统计查看每个库的内存占用情况。如果生产环境 buffer pool 很大，扫描会占用很多资源，造成性能问题，慎用。
- **innodbbufferstatsbytable** ：扫描整个 buffer pool 来统计查看每个库的每个对象的内存占用情况。如果生产环境 buffer pool 很大，扫描会占用很多资源，造成性能问题，慎用。
- **ioglobalbyfileby_bytes** ：查询数据库的 IO 情况。
- **memorybyhostbycurrent_bytes** ：查询连接数据库的主机内存情况。
- **memorybythreadbycurrent_bytes** ：查询连接数据库的线程内存情况。
- **memorybyuserbycurrent_bytes** ：查询连接数据库的用户内存情况。
- **processlist** ：查询数据库连接情况。
- **session** ：查询连接数据库的会话情况。
- **schematablelock_waits** ：查询锁等待情况。
- **schematablestatistics** ：查询对表的 insert、update、delete、select 的 IO 情况。
- **schematableswithfulltable_scans** ：查询全表扫描情况。
- **schemaautoincrement_columns** ：查询自增列情况。
- **schemaobjectoverview** ：查询 MySQL 中每个数据库的对象情况（包括表、索引、视图、函数、存储过程、触发器）。
- **schemaredundantindexes** ：查询数据库的冗余索引情况。
- **schemaunusedindexes** ：查询数据库中没有使用索引的情况。
- **schemaindexstatistics** ：查询索引的 select、insert、update、delete 情况。
- **statement_analysis** ：查询执行语句总体的统计信息情况。
- **statementswitherrorsorwarnings** ：查询执行语句的错误和警告情况。
- **statementswithfulltablescans** ：查询全表扫描情况。
- **statementswithruntimesin95th_percentile** ：查询语句平均执行时间大于整体 95%平均分布的情况。
- **statementswithsorting** ：查询使用了文件排序的情况。
- **statementswithtemp_tables** ：查询使用了临时表的执行语句情况。
- **user_summary** ：查询连接的总体执行时间、平均执行时间、IO、内存等情况。
- **version** ：查询 sys schema 和 MySQL 版本情况。
- **waitclassesglobalbyavg_latency** ：查询等待事件的平均延迟时间情况。
- **waitclassesglobalbylatency** ：查询等待事件的总体延迟时间情况。

以上差不多就是 sys 库常用的视图了，基本满足我们的日常分析统计需求，大家可以通过官网继续深入学习，学好这一部分的内容，对 MySQL 的底层原理及性能分析有非常大的帮助。
