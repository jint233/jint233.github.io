# MySQL 故障诊断：一个 ALTER TALBE 执行了很久，你慌不慌？

### 先了解下 MySQL 数据字典

当我们对一张大表执行了一个 ALTER TABLE 操作，执行了很久，也不知道是否执行完成，进程在那挂着，此时的你，干瞪眼，进度看不到，进程不敢杀，就问你慌不慌？

在具体解决这个慌乱之前，我们先了解下 MySQL 的数据字典。

数据字典我们用一句话来概括，就是数据的数据，用于查询数据库中数据的信息内容。

MySQL 在 5.7 开始，对数据字典的使用有了很大的改进，使用上更加的方便，提供的能力也更高。performance_schema 可以查询事务信息、获取元数据锁、跟踪事件、统计内存使用情况等等。

到这里你是不是发现了什么？

performance_schema 这个是什么，是不是用它来让我们解除慌张？

有关 MySQL 数据字典，可以看我的另外一个 Chat：

> \[MySQL 地基基础：数据字典\](./MySQL 地基基础：数据字典.md)

### 使用一些重要的重要功能

既然了解到 MySQL 数据字典可以帮助我们，那它是如何实现呢？

我们先看看官网是如何解释的

> [https://dev.mysql.com/doc/refman/5.7/en/monitor-alter-table-performance-schema.html](https://dev.mysql.com/doc/refman/5.7/en/monitor-alter-table-performance-schema.html)
>
> You can monitor ALTER TABLE progress for InnoDB tables using Performance Schema.
>
> There are seven stage events that represent different phases of ALTER TABLE. Each stage event reports a running total of WOR_COMPLETED and WORK_ESTIMATED for the overall ALTER TABLE operation as it progresses through its different phases. WORK_ESTIMATED is calculated using a formula that takes into account all of the work that ALTER TABLE performs, and may be revised during ALTER TABLE processing. WORK_COMPLETED and WORK_ESTIMATED values are an abstract representation of all of the work performed by ALTER TABLE.

大意就是我们可以在 Performance Schema 看到 ALTER TABLE 的进度，包括执行的时间，大概剩余的时间。

想要使用这个能力，我们需要开启几个功能。

**Enable the stage/innodb/alter% instruments** 

```sql
mysql> UPDATE performance_schema.setup_instruments
```

->        SET ENABLED = 'YES'
->        WHERE NAME LIKE 'stage/innodb/alter%';

```plaintext
Query OK, 0 rows affected (0.01 sec)

Rows matched: 7  Changed: 0  Warnings: 0
```

**Enable the stage event consumer tables** 

```sql
mysql> UPDATE performance_schema.setup_consumers
```

->        SET ENABLED = 'YES'
->        WHERE NAME ='events_stages_current';

```sql
Query OK, 1 row affected (0.00 sec)

Rows matched: 1  Changed: 1  Warnings: 0
mysql> UPDATE performance_schema.setup_consumers
```

->        SET ENABLED = 'YES'
->        WHERE NAME ='events_stages_history';

```sql
Query OK, 1 row affected (0.01 sec)

Rows matched: 1  Changed: 1  Warnings: 0
mysql> UPDATE performance_schema.setup_consumers
```

->        SET ENABLED = 'YES'
->        WHERE NAME ='events_stages_history_long';

```plaintext
Query OK, 1 row affected (0.00 sec)

Rows matched: 1  Changed: 1  Warnings: 0
```

功能开启了，接下来我们进行直观的验证环节。
### 直观的观察事件执行进度
首先，我们有一张大表（你可以用 SysBench 建一个，或者其他各种途径都可以），这里我已经有一张大表 sbtest.sbtest1，表结构如下：

```plaintext
mysql> desc sbtest.sbtest1;

+-------+-----------+------+-----+---------+----------------+

| Field | Type      | Null | Key | Default | Extra          |

+-------+-----------+------+-----+---------+----------------+

| id    | int(11)   | NO   | PRI | NULL    | auto_increment |

| k     | int(11)   | NO   | MUL | 0       |                |

| c     | char(120) | NO   |     |         |                |

| pad   | char(60)  | NO   |     |         |                |

+-------+-----------+------+-----+---------+----------------+

4 rows in set (0.00 sec)
```

数据量 500W：

```sql
mysql> select count(\*) from  sbtest.sbtest1;

+----------+

| count(\*) |

+----------+

|  5000000 |

+----------+

1 row in set (0.67 sec)
```

新增一个字段：

```sql
mysql> alter table sbtest.sbtest1 add d char(20);
```

重头戏来了，查看一下进度：

```sql
mysql> select * from performance_schema.events_stages_current\\G;

****  ****  ****  ****  ****  ****  ***1. row**  ****  ****  ****  ****  ****  **** *
```

THREAD_ID: 28
      EVENT_ID: 14
  END_EVENT_ID: NULL
    EVENT_NAME: stage/innodb/alter table (read PK and internal sort)
        SOURCE: 
   TIMER_START: 159726265417733000
     TIMER_END: 159819571346680000
    TIMER_WAIT: 93305928947000
WORK_COMPLETED: 118256
WORK_ESTIMATED: 302958

```sql
NESTING_EVENT_ID: 13

NESTING_EVENT_TYPE: STATEMENT

1 row in set (0.00 sec)
......
mysql> select * from performance_schema.events_stages_current\\G;

****  ****  ****  ****  ****  ****  ***1. row**  ****  ****  ****  ****  ****  **** *
```

THREAD_ID: 28
      EVENT_ID: 14
  END_EVENT_ID: NULL
    EVENT_NAME: stage/innodb/alter table (read PK and internal sort)
        SOURCE: 
   TIMER_START: 159726265417733000
     TIMER_END: 159910492100061000
    TIMER_WAIT: 184226682328000
WORK_COMPLETED: 230688
WORK_ESTIMATED: 302958

```plaintext
NESTING_EVENT_ID: 13

NESTING_EVENT_TYPE: STATEMENT

1 row in set (0.01 sec)
```

多执行几次，发现数据是有变化的，这些内容代表了什么呢？
*   THREAD\_ID：线程 ID
*   EVENT\_ID：事件 ID
*   END\_EVENT\_ID：结束事件 ID
*   EVENT\_NAME：事件名称，说明了当前执行的事件
*   SOURCE：源码位置
*   TIMER\_START：事件开始时间（皮秒）
*   TIMER\_END：事件结束时间（皮秒，如果没有执行完成，时间就是当前之间）
*   TIMER\_WAIT：事件等待事件（皮秒）
*   WORK\_COMPLETED：任务完成情况
*   WORK\_ESTIMATED：任务估算情况
*   NESTING\_EVENT\_ID：事件对应的父事件 ID
*   NESTING\_EVENT\_TYPE：父事件类型（STATEMENT、STAGE、WAIT）
### 收下这个常用的 SQL
1.  查看事件任务完成情况：

```sql
mysql> SELECT pt.INFO, ec.THREAD_ID, ec.EVENT_NAME, ec.WORK_COMPLETED, ec.WORK_ESTIMATED, pt.STATE FROM performance_schema.events_stages_current ec left join performance_schema.threads th on ec.thread_id = th.thread_id left join information_schema.PROCESSLIST pt on th.PROCESSLIST_ID = pt.ID where pt.INFO like 'ALTER%';

+-------------------------------------------+-----------+------------------------------------------------------+----------------+----------------+----------------+

| INFO                                      | THREAD_ID | EVENT_NAME                                           | WORK_COMPLETED | WORK_ESTIMATED | STATE          |

+-------------------------------------------+-----------+------------------------------------------------------+----------------+----------------+----------------+

| alter table sbtest.sbtest1 add d char(20) |        28 | stage/innodb/alter table (read PK and internal sort) |         201496 |         308223 | altering table |

+-------------------------------------------+-----------+------------------------------------------------------+----------------+----------------+----------------+

1 row in set (0.25 sec)
```

2.  查看任务完成事件：

```sql
mysql> select stmt.sql_text as sql_text, concat(work_completed, '/' , work_estimated) as progress, (stage.timer_end - stmt.timer_start) / 1e12 as current_seconds, (stage.timer_end - stmt.timer_start) / 1e12 * (work_estimated-work_completed) / work_completed as remaining_seconds from performance_schema.events_stages_current stage, performance_schema.events_statements_current stmt where stage.thread_id = stmt.thread_id and stage.nesting_event_id = stmt.event_id;

+-------------------------------------------+---------------+-----------------+--------------------+

| sql_text                                  | progress      | current_seconds | remaining_seconds  |

+-------------------------------------------+---------------+-----------------+--------------------+

| alter table sbtest.sbtest1 add d char(20) | 135192/308223 |   102.461512532 | 131.13954949201502 |

+-------------------------------------------+---------------+-----------------+--------------------+

1 row in set (0.00 sec)
```

### 总结
这样我们通过 MySQL 的这个数据字典就可以很直观地看到 ALTER 的执行情况了，当你看到这样的执行进度，是不是就不那么慌了。
```
