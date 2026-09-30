# MySQL 性能优化：碎片整理

## MySQL 碎片是什么

MySQL 碎片是数据文件中不连续的空白空间。这些空间无法被充分利用，久而久之会越来越多、越来越零碎，造成物理存储和逻辑存储的位置顺序不一致。

### 碎片是如何产生的

**delete 操作：** 删除数据后，存储中会产生空白空间。插入新数据时，MySQL 会尝试复用这些空间，但未必能全部填满。长期积累或大量删除后，空白空间可能变得很多，甚至超过表中数据占用的空间。

**update 操作：** 更新可变长度字段（例如 `VARCHAR`）时，InnoDB 可能会发生页分裂，使数据存储变得不连续、不规则，从而产生碎片。例如，原字段长度为 `VARCHAR(100)`，更新后数据长度为 50，剩余空间可能无法被新数据充分利用。

### 碎片到底产生了什么影响

碎片会带来以下影响：

- **空间浪费：** 碎片占用了可用空间。
- **读写性能下降：** 数据从连续、规则的存储方式变为随机分散的存储方式后，磁盘 I/O 会更加繁忙，数据库读写性能也会下降。

### 找一找有哪些碎片

现在我们有一个测试库 employees，在找碎片清理碎片前我们先查询一下表的数据，记录一下时间，以便后边做对比。

```sql
mysql> select count(*) from current_dept_emp;
+----------+
| count(*) |
+----------+
|   300024 |
+----------+
1 row in set (1.17 sec)
mysql> select count(*) from departments;
+----------+
| count(*) |
+----------+
|        9 |
+----------+
1 row in set (0.00 sec)
mysql> select count(*) from dept_emp;
+----------+
| count(*) |
+----------+
|   331603 |
+----------+
1 row in set (0.08 sec)
mysql> select count(*) from dept_emp_latest_date;
+----------+
| count(*) |
+----------+
|   300024 |
+----------+
1 row in set (0.49 sec)
mysql> select count(*) from dept_manager;
+----------+
| count(*) |
+----------+
|       24 |
+----------+
1 row in set (0.00 sec)
mysql> select count(*) from employees;
+----------+
| count(*) |
+----------+
|   300024 |
+----------+
1 row in set (0.09 sec)
mysql> select count(*) from salaries;
+----------+
| count(*) |
+----------+
|  2844047 |
+----------+
1 row in set (0.60 sec)
mysql> select count(*) from titles;
+----------+
| count(*) |
+----------+
|   443308 |
+----------+
1 row in set (0.11 sec)
```

接下来我们开始看看都有哪些碎片吧。这里介绍两种方式查看表碎片。

#### 1. 通过表状态信息查看

```text
show table status like '%table_name%';
mysql> show table status like 'salaries'\G
*************************** 1. row ***************************
Name: salaries
Engine: InnoDB
Version: 10
Row_format: Dynamic
Rows: 2838918
Avg_row_length: 31
Data_length: 90832896
Max_data_length: 0
Index_length: 0
Data_free: 4194304
Auto_increment: NULL
Create_time: 2021-01-14 14:33:47
Update_time: 2021-01-14 14:34:42
Check_time: NULL
Collation: utf8_bin
Checksum: NULL
Create_options:
Comment:
1 row in set (0.00 sec)
```

返回信息中的 `Data_length` 表示数据大小，`Index_length` 表示索引大小，`Data_free` 表示碎片大小。这里的碎片大小为 4194304 B。

#### 2. 通过数据库视图信息查看

查询 `information_schema.tables` 中的 `data_free` 列：

```text
mysql> select
t.table_schema,
t.table_name,
t.table_rows,
t.data_length,
t.index_length,
concat(round(t.data_free/1024/1024,2),'m') as data_free
from information_schema.tables t
where t.table_schema = 'employees';
+--------------+----------------------+------------+-------------+--------------+-----------+
| TABLE_SCHEMA | TABLE_NAME           | TABLE_ROWS | DATA_LENGTH | INDEX_LENGTH | DATA_FREE |
+--------------+----------------------+------------+-------------+--------------+-----------+
| employees    | current_dept_emp     |       NULL |        NULL |         NULL | NULL      |
| employees    | departments          |          9 |       16384 |        16384 | 0.00M     |
| employees    | dept_emp             |     331143 |    12075008 |      5783552 | 4.00M     |
| employees    | dept_emp_latest_date |       NULL |        NULL |         NULL | NULL      |
| employees    | dept_manager         |         24 |       16384 |        16384 | 0.00M     |
| employees    | employees            |     299069 |    15220736 |            0 | 4.00M     |
| employees    | salaries             |    2838426 |   100270080 |            0 | 4.00M     |
| employees    | titles               |     442902 |    20512768 |            0 | 4.00M     |
+--------------+----------------------+------------+-------------+--------------+-----------+
8 rows in set (0.01 sec)
```

根据结果显示，data_free 列数据就是我们要查询的表的碎片大小内容，是 4M。

### 如何清理碎片

找到表碎片后，可以通过以下两种方法清理。

#### 1. 分析表

执行命令：

```sql
optimize table table_name;
```

这个方法主要针对 MyISAM 引擎表使用，因为 MyISAM 表的数据和索引是分离的，optimize 表可以整理数据文件，重新排列索引。
注意：`OPTIMIZE TABLE` 会锁表，耗时取决于表的数据量。

#### 2. 重建表引擎

执行命令：

```sql
alter table table_name engine = innodb;
```

这个方法主要针对 InnoDB 引擎表使用，该操作会重建表的存储引擎，重组数据和索引的存储。
刚才查询到 `salaries` 表有 4 MB 碎片，下面清理该表：

```sql
mysql> alter table salaries engine = innodb;
```

查询一下该表的碎片是否被清理：

```text
mysql> select
t.table_schema,
t.table_name,
t.table_rows,
t.data_length,
t.index_length,
concat(round(t.data_free/1024/1024,2),'m') as data_free
from information_schema.tables t
where t.table_schema = 'employees' and table_name='salaries';
+--------------+------------+------------+-------------+--------------+-----------+
| table_schema | table_name | table_rows | data_length | index_length | data_free |
+--------------+------------+------------+-------------+--------------+-----------+
| employees    | salaries   |    2838426 |   114950144 |            0 | 2.00m     |
+--------------+------------+------------+-------------+--------------+-----------+
1 row in set (0.00 sec)
```

碎片从原来的 4M 清理到现在的 2M。
再查询一次，比较查询速度：

```sql
mysql> select count(*) from salaries;
+----------+
| count(*) |
+----------+
|  2844047 |
+----------+
1 row in set (0.16 sec)
```

清理碎片后，查询速度有所提高。

**总结：** 定期整理表碎片可以改善 MySQL 的存储空间利用率和查询性能。
