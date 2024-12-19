# MySQL 性能优化：碎片整理

### MySQL 碎片是什么

MySQL 碎片就是 MySQL 数据文件中一些不连续的空白空间，这些空间无法再被全部利用，久而久之越来多，越来越零碎，从而造成物理存储和逻辑存储的位置顺序不一致，这就是碎片。

### 碎片是如何产生的

**delete 操作** 在 MySQL 中删除数据，在存储中就会产生空白的空间，当有新数据插入时，MySQL 会试着在这些空白空间中保存新数据，但是呢总是用不满这些空白空间。所以日积月累，亦或是一下有大量的 delete 操作，一下就会有大量的空白空间，慢慢的会大到比表的数据使用的空间还大。 **update 操作** 在 MySQL 中更新数据，在可变长度的字段（比如 varchar）中更新数据，innodb 表存储数据的单位是页，update 操作会造成页分裂，分裂以后存储变的不连续，不规则，从而产生碎片。比如说原始字段长度 varchar(100)，我们大量的更新数据长度位为 50，这样的话，有 50 的空间被空白了，新入库的数据不能完全利用剩余的 50，这就会产生碎片。

### 碎片到底产生了什么影响

MySQL 既然产生了碎片，你可能比较豪横说磁盘空间够大，浪费空间也没事，但是这些碎片也会产生性能问题，碎片会有什么影响呢？ **空间浪费** 空间浪费不用多说，碎片占用了大量可用空间。 **读写性能下降**

由于存在大量碎片，数据从连续规则的存储方式变为随机分散的存储方式，磁盘 IO 会变的繁忙，数据库读写性能就会下降。

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

**1. 通过表状态信息查看** 

```plaintext
show table status like '%table_name%';
mysql> show table status like 'salaries'\\G; ****  ****  ****  ****  ****  ****  ***1. row**  ****  ****  ****  ****  ****  **** *Name: salaries
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

data_length 表数据大小 index_length 表索引大小 data\_free 碎片大小
根据返回信息，我们知道碎片大小为 4194304（单位 B） **2. 通过数据库视图信息查看** 查询 information\_schema.tables 的 data\_free 列的值：

```python
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

根据结果显示，data\_free 列数据就是我们要查询的表的碎片大小内容，是 4M。
### 如何清理碎片
找到表碎片了，我们如何清理呢？有两种方法。 **1. 分析表** 命令：

```plaintext
optimize table table_name;
```

这个方法主要针对 MyISAM 引擎表使用，因为 MyISAM 表的数据和索引是分离的，optimize 表可以整理数据文件，重新排列索引。
注意：optimize 会锁表，时间长短依据表数据量的大小。 **2. 重建表引擎** 命令：

```sql
alter table table_name engine = innodb;
```

这个方法主要针对 InnoDB 引擎表使用，该操作会重建表的存储引擎，重组数据和索引的存储。
刚才我们查到表 salaries 有 4M 的碎片，我们清理一下 salaries 表碎片：

```sql
mysql> alter table salaries engine = innodb;
```

查询一下该表的碎片是否被清理：

```python
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
我们看看查询表是否提高了速度：

```sql
mysql> select count(*) from salaries;
+----------+
| count(*) |
+----------+
|  2844047 |
+----------+
1 row in set (0.16 sec)
```

速度还是提高了不少，清理碎片后提高了查询速度。 **总结一下** ：清理表的碎片可以提高 MySQL 性能，在日常工作中我们可以定期执行表碎片整理，从而提高 MySQL 性能。
```
