# MySQL 主从复制 基于 GTID 复制

相比传统的 MySQL 复制，gtid 复制无论是配置还是维护都要轻松的多。本文对 gtid 复制稍作介绍。

MySQL 基于 GTID 复制官方手册：[https://dev.mysql.com/doc/refman/5.7/en/replication-gtids.html](https://dev.mysql.com/doc/refman/5.7/en/replication-gtids.html)

# 1.gtid 基本概念

传统的基于 binlog position 复制的方式有个严重的缺点：如果 slave 连接 master 时指定的 binlog 文件错误或者 position 错误，会造成遗漏或者重复，很多时候前后数据是有依赖性的，这样就会出错而导致数据不一致。

从 MYSQL5.6 开始，mysql 开始支持 GTID 复制。GTID 的全称是 global transaction id，表示的是全局事务 ID。GTID 的分配方式为`uuid:trans_id`，其中：

- `uuid`是每个 mysql 服务器都唯一的，记录在`$datadir/auto.cnf`中。如果复制结构中，任意两台服务器 uuid 重复的话(比如直接冷备份时，auto.conf 中的内容是一致的)，在启动复制功能的时候会报错。这时可以删除 auto.conf 文件再重启 mysqld。

```plaintext
mysql> show variables like "%uuid%";       
+---------------+--------------------------------------+
| Variable_name | Value                                |
+---------------+--------------------------------------+
| server_uuid   | a126fcb6-3706-11e8-b1d5-000c294ebf0d |
+---------------+--------------------------------------+
1 row in set (0.00 sec)
　
mysql> \! cat /data/auto.cnf
[auto]
server-uuid=a126fcb6-3706-11e8-b1d5-000c294ebf0d
```

- `trans_id`是事务 ID，可以唯一标记某 MySQL 服务器上执行的某个事务。事务号从 1 开始，每提交一个事务，事务号加 1。

例如"gtid_executed 5ad9cb8e-2092-11e7-ac95-000c29bf823d:1-6"，表示该 server_uuid 上执行了从 1 到 6 的事务。

# 2.gtid 的生命周期

**gtid 的生命周期对于配置和维护基于 gtid 的复制至关重要**。所以，请尽可能理解以下几个过程。

gtid 在 master 和 slave 上是一直 **持久化保存** (即使删除了日志，也会记录到 Previous_GTID 中)的。它在 master 和 slave 上的生命周期如下：

1. 客户端发送 DDL/DML 给 master 上，master 首先对此事务生成一个唯一的 gtid，假如为`uuid_xxx:1`，然后立即执行该事务中的操作。

   注意，主从复制的情况下，sync-binlog 基本上都会设置为 1，这表示在每次提交事务时将缓存中的 binlog 刷盘。所以，在事务提交前，gtid 以及事务相关操作的信息都在缓存中，提交后它们才写入到 binlog file 中，然后才会被 dump 线程 dump 出去。

   换句话说，**只有提交了的事务，gtid 和对应的事务操作才会记录到 binlog 文件中。记录的格式是先记录 gtid，紧跟着再记录事务相关的操作。** 2.  当 binlog 传送到 relay log 中后，slave 上的 SQL 线程首先读取该 gtid，并设置变量 _gtid_next_ 的值为该 gtid，表示下一个要操作的事务是该 gtid。 _gtid_next_ **是基于会话的，不同会话的 gtid_next 不同。** 3.  随后 slave 检测该 gtid 在自己的 binlog 中是否存在。如果存在，则放弃此 gtid 事务；如果不存在，则将此 gtid 写入到 **自己的 binlog 中**，然后立刻执行该事务，并在自己的 binlog 中记录该事务相关的操作。

   注意，**slave 上 replay 的时候，gtid 不是提交后才写到自己的 binlog file 的，而是判断 gtid 不存在后立即写入 binlog file。** 通过这种在执行事务前先检查并写 gtid 到 binlog 的机制，不仅可以保证当前会话在此之前没有执行过该事务，还能保证没有其他会话读取了该 gtid 却没有提交。因为如果其他会话读取了该 gtid 会立即写入到 binlog(不管是否已经开始执行事务)，所以当前会话总能读取到 binlog 中的该 gtid，于是当前会话就会放弃该事务。总之，一个 gtid 事务是决不允许多次执行、多个会话并行执行的。

2. slave 在重放 relay log 中的事务时，不会自己生成 gtid，所以所有的 slave(无论是何种方式的一主一从或一主多从复制架构)通过重放 relay log 中事务获取的 gtid 都来源于 master，并永久保存在 slave 上。

# 3.基于 gtid 复制的好处

从上面可以看出，gtid 复制的优点大致有：

1. **保证同一个事务在某 slave 上绝对只执行一次，没有执行过的 gtid 事务总是会被执行。** 2. **不用像传统复制那样保证 binlog 的坐标准确，因为根本不需要 binlog 以及坐标。** 3. **故障转移到新的 master 的时候很方便，简化了很多任务。** 4. **很容易判断 master 和 slave 的数据是否一致。只要 master 上提交的事务在 slave 上也提交了，那么一定是一致的。**

当然，MySQL 提供了选项可以控制跳过某些 gtid 事务，防止 slave 第一次启动复制时执行 master 上的所有事务而导致耗时过久。

虽然对于 row-based 和 statement-based 的格式都能进行 gtid 复制，但建议采用 row-based 格式。

# 4.配置一主一从的 gtid 复制

环境：

主机 IP

OS 版本

MySQL 版本

角色(master/slave)

数据状态

192.168.100.21

centos 7

MySQL 5.7.22

master_gtid

全新实例

192.168.100.22

centos 7

MySQL 5.7.22

slave1_gtid

全新实例

因为是用作 master 和 slave 的 mysql 实例都是全新环境，所以这里简单配置一下即可。

master 的配置文件：

```plaintext
[mysqld]
datadir=/data
socket=/data/mysql.sock
log-bin=/data/master-bin      # 必须项
sync-binlog=1                 # 建议项
binlog_format=row             # 建议项
server-id=100                 # 必须项
log-error=/data/error.log
pid-file=/data/mysqld.pid
enforce_gtid_consistency=on   # gtid复制需要加上的必须项
gtid_mode=on                  # gtid复制需要加上的必须项
```

关于后面的两项，是 gtid 复制所必须开启的项，这里指定它开启就行了，它们的意义以及更多 gtid 相关的选项见后文解释。

slave 的配置文件：

```plaintext
[mysqld]
datadir=/data
socket=/data/mysql.sock
log-bin=/data/master-slave-bin    # mysql 5.6必须项，mysql 5.7非必须项
sync-binlog=1                     # 建议项
binlog_format=row                 # 建议项
relay-log=/data/slave-bin         # 必须项
server-id=110                     # 必须项
log-error=/data/error.log
pid-file=/data/mysqld.pid
enforce_gtid_consistency=on       # 必须项
gtid_mode=on                      # 必须项
```

我的环境是 mysql 5.7，如果是 mysql 5.6，那么在上面两个配置文件中需要加上`log-slave-updates`选项。

重启 master 和 slave 后，在 master 上创建一个用于复制的用户`repl`。

```mysql
# master上执行
mysql> grant replication slave on *.* to [email protected]'192.168.100.%' identified by '[email protected]!';
```

因为 master 上的 binlog 没有删除过，所以在 slave 上直接`change master to`配置连接参数。

```mysql
# slave上执行
mysql> change master to 
        master_host='192.168.100.21',
        master_port=3306,
        master_auto_position=1;    # gtid复制必须设置此项
```

因为是 MySQL 5.7，没有在`change master to`语句中加入 user 和 password 项，而是在`start slave`语句中使用，否则会警告。

现在启动 slave 上的两个复制线程。

```mysql
# slave上执行
mysql> start slave user='repl' password='[email protected]!';
```

查看 io 线程和 sql 线程是否正常。

```plaintext
# slave上执行，为了排版，缩减了一些无关紧要的字段
mysql> show processlist;
+----+-------------+---------+--------------------------------------------------------+
| Id | User        | Command | State                                                  |
+----+-------------+---------+--------------------------------------------------------+
|  9 | root        | Query   | starting                                               |
| 10 | system user | Connect | Waiting for master to send event                       |
| 11 | system user | Connect | Slave has read all relay log; waiting for more updates |
+----+-------------+---------+--------------------------------------------------------+
```

最后验证 gtid 复制是否生效。

在 master 上插入一些数据。这里使用[上一篇文章](https://www.cnblogs.com/f-ck-need-u/p/9155003.html)中使用的存储过程`proc_num1`和`proc_num2`分别向数值辅助表`backup.num_isam`和`backup.num_innodb`中插入一些数据，该存储过程的代码见：[https://www.cnblogs.com/f-ck-need-u/p/9155003.html#blognum。](https://www.cnblogs.com/f-ck-need-u/p/9155003.html#blognum%E3%80%82)

```plaintext
# 向MyISAM数值辅助表backup.num_isam插入100W行数据
call proc_num1(1000000);
# 向InnoDB数值辅助表backup.num_innodb插入100W行数据
call proc_num2(1000000);
```

在 slave 上查看 slave 的状态，以下是同步结束后的状态信息。

```plaintext
# slave上执行：
mysql> show slave status\G ****  ****  ****  ****  ****  ****  ***1. row**  ****  ****  ****  ****  ****  **** *
               Slave_IO_State: Waiting for master to send event
                  Master_Host: 192.168.100.21
                  Master_User: repl
                  Master_Port: 3306
                Connect_Retry: 60
              Master_Log_File: master-bin.000004
          Read_Master_Log_Pos: 10057867
               Relay_Log_File: slave-bin.000003
                Relay_Log_Pos: 457
        Relay_Master_Log_File: master-bin.000004
             Slave_IO_Running: Yes
            Slave_SQL_Running: Yes
              Replicate_Do_DB: 
          Replicate_Ignore_DB: 
           Replicate_Do_Table: 
       Replicate_Ignore_Table: 
      Replicate_Wild_Do_Table: 
  Replicate_Wild_Ignore_Table: 
                   Last_Errno: 0
                   Last_Error: 
                 Skip_Counter: 0
          Exec_Master_Log_Pos: 10057867
              Relay_Log_Space: 10058586
              Until_Condition: None
               Until_Log_File: 
                Until_Log_Pos: 0
           Master_SSL_Allowed: No
           Master_SSL_CA_File: 
           Master_SSL_CA_Path: 
              Master_SSL_Cert: 
            Master_SSL_Cipher: 
               Master_SSL_Key: 
        Seconds_Behind_Master: 0
Master_SSL_Verify_Server_Cert: No
                Last_IO_Errno: 0
                Last_IO_Error: 
               Last_SQL_Errno: 0
               Last_SQL_Error: 
  Replicate_Ignore_Server_Ids: 
             Master_Server_Id: 100
                  Master_UUID: a659234f-6aea-11e8-a361-000c29ed4cf4
             Master_Info_File: /data/master.info
                    SQL_Delay: 0
          SQL_Remaining_Delay: NULL
      Slave_SQL_Running_State: Slave has read all relay log; waiting for more updates
           Master_Retry_Count: 86400
                  Master_Bind: 
      Last_IO_Error_Timestamp: 
     Last_SQL_Error_Timestamp: 
               Master_SSL_Crl: 
           Master_SSL_Crlpath: 
           Retrieved_Gtid_Set: a659234f-6aea-11e8-a361-000c29ed4cf4:1-54
            Executed_Gtid_Set: a659234f-6aea-11e8-a361-000c29ed4cf4:1-54
                Auto_Position: 1
         Replicate_Rewrite_DB: 
                 Channel_Name: 
           Master_TLS_Version:
```

# 5.添加新的 slave 到 gtid 复制结构中

GTID 复制是基于事务 ID 的，确切地说是 binlog 中的 GTID，所以事务 ID 对 GTID 复制来说是命脉。

当 master 没有删除过任何 binlog 时，可以随意地向复制结构中添加新的 slave，因为 slave 会复制所有的 binlog 到自己 relay log 中并 replay。这样的操作尽管可能速度不佳，但胜在操作极其简便。

当 master 删除过一部分 binlog 后，在向复制结构中添加新的 slave 时，必须先获取到 master binlog 中当前已记录的第一个 gtid 之前的所有数据，然后恢复到 slave 上。只有 slave 上具有了这部分基准数据，才能保证和 master 的数据一致性。

而在实际环境中，往往会定期删除一部分 binlog。所以，为了配置更通用的 gtid 复制环境，这里把前文的 master 的 binlog 给 purge 掉一部分。

目前 master 上的 binlog 使用情况如下，不难发现绝大多数操作都集中在`master-bin.000004`这个 binlog 中。

```plaintext
[[email protected] ~]# ls -l /data/*bin*
-rw-r----- 1 mysql mysql      177 Jun  8 15:07 /data/master-bin.000001
-rw-r----- 1 mysql mysql      727 Jun  8 15:42 /data/master-bin.000002
-rw-r----- 1 mysql mysql      177 Jun  9 09:50 /data/master-bin.000003
-rw-r----- 1 mysql mysql 10057867 Jun  9 10:17 /data/master-bin.000004
-rw-r----- 1 mysql mysql       96 Jun  9 09:50 /data/master-bin.index
```

purge 已有的 binlog。

```plaintext
mysql> flush logs;
mysql> purge master logs to 'master-bin.000005';
[[email protected] ~]# cat /data/master-bin.index 
/data/master-bin.000005
```

但无论 master 是否 purge 过 binlog，配置基于 gtid 的复制都极其方便，而且方法众多(只要理解了 GTID 的生命周期，可以随意折腾，基本上都能很轻松地维护好)，这是它"迷人"的优点。

现在的测试环境是这样的：

主机 IP

OS 版本

MySQL 版本

角色(master/slave)

数据状态

192.168.100.21

centos 7

MySQL 5.7.22

master_gtid

已 purge 过 binlog

192.168.100.22

centos 7

MySQL 5.7.22

slave1_gtid

已同步

192.168.100.23

centos 7

MySQL 5.7.22

slave2_gtid

全新实例

其中 slave2 的配置文件和 slave1 的配置文件完全相同：

```plaintext
[mysqld]
datadir=/data
socket=/data/mysql.sock
log-bin=/data/master-slave-bin    # 必须项
sync-binlog=1                     # 建议项
binlog_format=row                 # 建议项
relay-log=/data/slave-bin         # 必须项
server-id=110                     # 必须项
log-error=/data/error.log
pid-file=/data/mysqld.pid
enforce_gtid_consistency=on       # 必须项
gtid_mode=on                      # 必须项
```

**1.备份 master。** 我选择的是 xtrabackup 的 innobackupex 工具，因为它速度快，操作简单，而且在线备份也比较安全。如果不知道 xtrabackup 备份的使用方法，见我的另一篇文章：[xtrabackup 用法和原理详述](https://www.cnblogs.com/f-ck-need-u/p/9018716.html)。当然，你也可以采用 mysqldump 和冷备份的方式，因为 gtid 复制的特性，这些备份方式也都很安全。

```plaintext
# master上执行，备份所有数据：
[[email protected] ~]# mkdir /backdir   # 备份目录
[[email protected] ~]# innobackupex -uroot [email protected]! -S /data/mysql.sock /backdir/  # 准备数据
[[email protected] ~]# innobackupex --apply-log /backdir/2018-06-09_20-02-24/   # 应用数据
[[email protected] ~]# scp -pr /backdir/2018-06-09_20-02-24/ 192.168.100.23:/tmp
```

**2.将备份恢复到 slave2。**

在 slave2 上执行：

```plaintext
\[\[email protected\] ~\]# systemctl stop mysqld
\[\[email protected\] ~\]# rm -rf /data/\*    # 恢复前必须先清空数据目录
\[\[email protected\] ~\]# innobackupex --copy-back /tmp/2018-06-09_20-02-24/  # 恢复备份数据
\[\[email protected\] ~\]# chown -R mysql.mysql /data
\[\[email protected\] ~\]# systemctl start mysqld
```

**3.设置 gtid_purged，连接 master，开启复制功能。**

由于 xtrabackup 备份数据集却不备份 binlog，所以必须先获取此次备份结束时的最后一个事务 ID，并在 slave 上明确指定跳过这些事务，否则 slave 会再次从 master 上复制这些 binlog 并执行，导致数据重复执行。

可以从 slave2 数据目录中的`xtrabackup_info`文件中获取。如果不是 xtrabackup 备份的，那么可以直接从 master 的`show global variables like "gtid_executed";`中获取，它表示 master 中已执行过的事务。

```plaintext
\[\[email protected\] ~\]# cat /data/xtrabackup_info
uuid = fc3de8c1-6bdc-11e8-832d-000c29ed4cf4
name =
tool_name = innobackupex
tool_command = -uroot \[email protected\]! -S /data/mysql.sock /backdir/
tool_version = 2.4.11
ibbackup_version = 2.4.11
server_version = 5.7.22-log
start_time = 2018-06-09 20:02:28
end_time = 2018-06-09 20:02:30
lock_time = 0
binlog_pos = filename 'master-bin.000005', position '194', GTID of the last change 'a659234f-6aea-11e8-a361-000c29ed4cf4:1-54'
innodb_from_lsn = 0
innodb_to_lsn = 51235233
partial = N
incremental = N
format = file
compact = N
compressed = N
encrypted = N
```

其中`binlog_pos`中的 GTID 对应的就是已备份的数据对应的事务。换句话说，这里的 gtid 集合 1-54 表示这 54 个事务不需要进行复制。

或者在 master 上直接查看 executed 的值，注意不是 gtid_purged 的值，master 上的 gtid_purged 表示的是曾经删除掉的 binlog。

```plaintext
mysql> show global variables like '%gtid%';
+----------------------------------+-------------------------------------------+
| Variable_name                    | Value                                     |
+----------------------------------+-------------------------------------------+
| binlog_gtid_simple_recovery      | ON                                        |
| enforce_gtid_consistency         | ON                                        |
| gtid_executed                    | a659234f-6aea-11e8-a361-000c29ed4cf4:1-54 |
| gtid_executed_compression_period | 1000                                      |
| gtid_mode                        | ON                                        |
| gtid_owned                       |                                           |
| gtid_purged                      | a659234f-6aea-11e8-a361-000c29ed4cf4:1-54 |
| session_track_gtids              | OFF                                       |
+----------------------------------+-------------------------------------------+
```

可以 **在启动 slave 线程之前使用 gtid_purged 变量来指定需要跳过的 gtid 集合。** 但因为要设置 gtid_purged 必须保证全局变量 gtid_executed 为空，所以先在 slave 上执行`reset master`(注意，不是 reset slave)，再设置 gtid_purged。

```plaintext
# slave2上执行

mysql> reset master;
mysql> set @@global.gtid_purged='a659234f-6aea-11e8-a361-000c29ed4cf4:1-54';
```

设置好 gtid_purged 之后，就可以开启复制线程了。

```plaintext
mysql> change master to
master_host='192.168.100.21',
master_port=3306,
master_auto_position=1;
mysql> start slave user='repl' password='\[email protected\]!';
```

查看 slave 的状态，看是否正确启动了复制功能。如果没错，再在 master 上修改一部分数据，检查是否同步到 slave1 和 slave2。

**4.回到 master，purge 掉已同步的 binlog。**

当 slave 指定 gtid_purged 并实现了同步之后，为了下次重启 mysqld 实例不用再次设置 gtid_purged(甚至可能会在启动的时候自动开启复制线程)，所以应该去 master 上将已经同步的 binlog 给 purged 掉。

```plaintext
# master上执行

mysql> flush logs;    # flush之后滚动到新的日志master-bin.000006

# 在确保所有slave都复制完000006之前的所有事务后，purge掉旧日志

mysql> purge master logs to "master-bin.000006";
```

6.GTID 复制相关的状态信息和变量
==================

6.1 `show slave status`中和 gtid 复制相关的状态行
-------------------------------------

```plaintext
Retrieved_Gtid_Set: a659234f-6aea-11e8-a361-000c29ed4cf4:1-54
Executed_Gtid_Set: a659234f-6aea-11e8-a361-000c29ed4cf4:1-54
Auto_Position: 1
```

其中：

*   `Retrieved_Gtid_Set`：在开启了 gtid 复制(即 gtid_mode=on)时，slave 在启动 io 线程的时候会检查自己的 relay log，并从中检索出 gtid 集合。也就是说，这代表的是 slave 已经从 master 中复制了哪些事务过来。检索出来的 gtid 不会再请求 master 发送过来。
*   `Executed_Gtid_Set`：在开启了 gtid 复制(即 gtid_mode=on)时，它表示已经向自己的 binlog 中写入了哪些 gtid 集合。注意，这个值是根据一些状态信息计算出来的，并非 binlog 中能看到的那些。举个特殊一点的例子，可能 slave 的 binlog 还是空的，但这里已经显示一些已执行 gtid 集合了。
*   `Auto_Position`：开启 gtid 时是否自动获取 binlog 坐标。1 表示开启，这是 gtid 复制的默认值。

6.2 binlog 中关于 gtid 的信息
--------------------

例如：

```sql
\[\[email protected\] ~\]# mysqlbinlog /data/master-bin.000007
/_!50530 SET @@SESSION.PSEUDO_SLAVE_MODE=1_/;
/_!50003 SET @\[email protected\]@COMPLETION_TYPE,COMPLETION_TYPE=0_/;
DELIMITER /_!_/;

# at 4

# 180610  1:34:08 server id 100  end_log_pos 123 CRC32 0x4a6e9510        Start: binlog v 4, server v 5.7.22-log created 180610  1:34:08

# Warning: this binlog is either in use or was not closed properly

BINLOG '
kA8cWw9kAAAAdwAAAHsAAAABAAQANS43LjIyLWxvZwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAEzgNAAgAEgAEBAQEEgAAXwAEGggAAAAICAgCAAAACgoKKioAEjQA
ARCVbko=
'/_!_/;

# at 123

# 180610  1:34:08 server id 100  end_log_pos 194 CRC32 0x0f6ba409        Previous-GTIDs

# a659234f-6aea-11e8-a361-000c29ed4cf4:1-57         #### 注意行1

# at 194

# 180610  2:06:31 server id 100  end_log_pos 259 CRC32 0xfef9194e        GTID    last_committed=0        sequence_number=1       rbr_only=no  #### 注意行2

SET @@SESSION.GTID_NEXT= 'a659234f-6aea-11e8-a361-000c29ed4cf4:58'/_!_/;   #### 注意行3

# at 259

# 180610  2:06:31 server id 100  end_log_pos 359 CRC32 0x5a561d94        Query   thread_id=2     exec_time=0     error_code=0

use `backup`/_!_/;
SET TIMESTAMP=1528567591/_!_/;
SET @@session.pseudo_thread_id=2/_!_/;
SET @@session.foreign_key_checks=1, @@session.sql_auto_is_null=0, @@session.unique_checks=1, @@session.autocommit=1/_!_/;
SET @@session.sql_mode=1436549152/_!_/;
SET @@session.auto_increment_increment=1, @@session.auto_increment_offset=1/_!_/;
/_!\\C utf8 _//_!_/;
SET @@session.character_set_client=33,@@session.collation_connection=33,@@session.collation_server=8/_!_/;
SET @@session.lc_time_names=0/_!_/;
SET @@session.collation_database=DEFAULT/_!_/;
create table t1(n int)
/_!_/;

# at 359

# 180610  2:09:36 server id 100  end_log_pos 424 CRC32 0x82564e69        GTID    last_committed=1        sequence_number=2       rbr_only=no     #### 注意行4

SET @@SESSION.GTID_NEXT= 'a659234f-6aea-11e8-a361-000c29ed4cf4:59'/_!_/;  #### 注意行5

# at 424

# 180610  2:09:36 server id 100  end_log_pos 524 CRC32 0xbc21683a        Query   thread_id=2     exec_time=0     error_code=0

SET TIMESTAMP=1528567776/_!_/;
create table t2(n int)
/_!_/;
SET @@SESSION.GTID_NEXT= 'AUTOMATIC' /_added by mysqlbinlog _/ /_!_/;   #### 注意行6
DELIMITER ;

# End of log file

/_!50003 SET \[email protected\]_COMPLETION_TYPE_/;
/_!50530 SET @@SESSION.PSEUDO_SLAVE_MODE=0_/;
```

其中：

*   "注意行 1"中`Previous-GTIDs`代表的 gtid 集合是曾经的 gtid，换句话说是被 purge 掉的事务。
*   "注意行 2"和"注意行 4"是两个事务的 gtid 信息。它们写在每个事务的前面。
*   "注意行 3"和"注意行 5"设置了 GTID_NEXT 的值，表示读取到了该事务后，那么必须要执行的是稍后列出的这个事务。
*   "注意行 6"是在所有事务执行结束时设置的，表示自动获取 gtid 的值。它对复制是隐身的(也就是说不会 dump 线程不会将它 dump 出去)，该行的结尾也说了，这一行是 mysqlbinlog 添加的。

6.3 一些重要的变量
-----------

*   `gtid_mode`：是否开启 gtid 复制模式。只允许 on/off 类的布尔值，不允许其他类型(如 1/0)的布尔值，实际上这个变量是枚举类型的。要设置 _gtid_mode=on_ ，必须同时设置 _enforce_gtid_consistency_ 开。在 MySQL 5.6 中，还必须开启 _log_slave_updates_ ，即使是 master 也要开启。

*   

```enforce_gtid_consistency
```

    ：强制要求只允许复制事务安全的事务。

    gtid_mode=on 时必须显式设置该项，如果不给定值，则默认为 on。应该尽量将该选项放在 gtid_mode 的前面，减少启动 mysqld 时的检查。

    *   不能在事务内部创建和删除临时表。只能在事务外部进行，且 autocommit 需要设置为 1。
    *   不能执行 _create table ... select_ 语句。该语句除了创建一张新表并填充一些数据，其他什么事也没干。
    *   不能在事务内既更新事务表又更新非事务表。
- `gtid_executed`：已经执行过的 GTID。 _reset master_ 会清空该项的全局变量值。

- `gtid_purged`：已经 purge 掉的 gtid。要设置该项，必须先保证 _gtid_executed_ 已经为空，这意味着也一定会同时设置该项为空。在 slave 上设置该项时，表示稍后启动 io 线程和 SQL 线程都跳过这些 gtid，slave 上设置时应该让此项的 gtid 集合等于 master 上 _gtid_executed_ 的值。

- `gtid_next`：表示下一个要执行的 gtid 事务。

需要注意，master 和 slave 上都有`gtid_executed`和`gtid_purged`，它们代表的意义有时候是不同的。

还有一些变量，可能用到的不会多。如有需要，可翻官方手册。

6.4 mysql.gtid_executed 表
-------------------------

MySQL 5.7 中添加了一张记录已执行 gtid 的表`mysql.gtid_executed`，所以 slave 上的 binlog 不是必须开启的。
```

mysql> select * from mysql.gtid_executed;
+--------------------------------------+----------------+--------------+
| source_uuid                          | interval_start | interval_end |
+--------------------------------------+----------------+--------------+
| a659234f-6aea-11e8-a361-000c29ed4cf4 |              1 |           57 |
| a659234f-6aea-11e8-a361-000c29ed4cf4 |             58 |           58 |
| a659234f-6aea-11e8-a361-000c29ed4cf4 |             59 |           59 |
+--------------------------------------+----------------+--------------+

```plaintext
7.一张图说明 GTID 复制
=============

在前面第 6 节中，使用了 xtrabackup 备份的方式提供 gtid 复制的基准数据。其中涉及到一些 gtid 检查、设置的操作。通过这些操作，大概可以感受的到 gtid 复制的几个概念。

用一张图来说明：

![img](../assets/733013-20180610232911355-1454041164.png)

假如当前 master 的 gtid 为 A3，已经 purge 掉的 gtid 为"1-->A1"，备份到 slave 上的数据为 1-A2 部分。

如果`A1 = 0`，表示 master 的 binlog 没有被 Purge 过。slave 可以直接开启 gtid 复制，但这样可能速度较慢，因为 slave 要复制所有 binlog。也可以将 master 数据备份到 slave 上，然后设置 _gtid_purged_ 跳过备份结束时的 gtid，这样速度较快。

如果`A1 != 0`，表示 master 上的 binlog 中删除了一部分 gtid。此时 slave 上必须先从 master 处恢复 purge 掉的那部分日志对应的数据。上图中备份结束时的 GTID 为 A2。然后 slave 开启复制，唯一需要考虑的是"是否需要设置 _gtid_purged_ 跳过一部分 gtid 以避免重复执行"。

备份数据到 slave 上，方式可以是 mysqldump、冷备份、xtrabackup 备份都行。由于 gtid 复制的特性，所需要的操作都很少，也很简单，前提是理解了"gtid 的生命周期"。
```

