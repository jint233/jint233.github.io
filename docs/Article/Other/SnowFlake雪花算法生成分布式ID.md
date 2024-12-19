# SnowFlake 雪花算法生成分布式 ID

### SnowFlake 雪花算法基本概念

SnowFlake 雪花算法是 Twitter 开源的分布式唯一 ID 生成算法，其具有简洁、高性能、低延迟、ID 按时间趋势有序等特点。如采用 12 位序列号，则理论支持每毫秒生成 4096 个不同数字，能够满足绝大多数高并发场景下的互联网应用。SnowFlake 雪花算法能保证在 datacenterId 和 workerId 唯一的情况下不会生成重复值。如果单位毫秒并发量 >4096，将会等到下一毫秒继续生成 ID。因此如果单台服务器并发量大于 4096/ms，是时候考虑自研算法了。

SnowFlake 的结构如下：

![在这里插入图片描述](../assets/50ba2570-e86c-11ea-8115-8d7d715b7847)

```plaintext
0 - 0000000000 0000000000 0000000000 0000000000 0 - 00000 - 00000 - 000000000000
```

总共 64 个 bit 位，对应于 Java 基本数据类型的 Long 类型 1 位符号位，正数是 0，负数是 1，id 一般是正数，因此最高位是 0 41 位时间戳（毫秒级），41 位时间戳不是存储当前时间的时间戳，而是存储时间戳差值（当前时间戳 - 开始时间戳）。开始时间戳一般是 Id 生成器开始投入使用的时间，可在程序中指定。

- 41 位时间戳，可以使用 69 年，年数 = (1L \<\< 41) / (1000L *60* 60 *24* 365) ≈ 69
- 10 位机器位，可以部署 1024 个节点，包括 5 位 datacenterId 和 5 位 workerId
- 12 位序列号，毫秒内计数，支持每个节点每毫秒产生 4096 个不重复 ID 序号

### 基于原版算法的改进

#### 增加毫秒内初始 id 随机生成

毫秒内初始 id 随机生成可以有效避免逆向工程导致 id 的可推测性。具体开发时通过可配置参数决定是否启用单位毫秒内随机生成起始 ID。随机生成的起始 ID 可能很大，会很快到达单位毫秒内的最大值，比如 4095（12 位序列号情况下），所以需要对 4095 处理，比如取模、或者和二进制位数&运算 循环使用单位毫秒内的可用数字，避免浪费。

#### 增加 workerId、datacenterId 自动生成

为了能够简单快捷地使用 SnowFlake 算法，可以基于 mac\\hostip\\jvmid 等信息自动生成 workerId、datacenterId，尽最大可能不重复。要完全保证 workerId、datacenterId 的唯一性还得借助第三方工具，比如 Redis、ZooKeeper 等开源中间件。

在单个数据中心机器数远 \<32 台、数据中心数远 \<32 个时，使用本文介绍的方法在不同机器上生成完全相同的 workerId、datacenterId 的概率极低。

具体开发时也保留原生接口，让使用者（比如业务系统）传入自行生成的 workerId、datacenterId ，调用方可以借助 Redis、ZK 等第三方中间件自行保证机器号和数据中心号唯一。

#### 时钟回拨处理

**运行时** 若偏差在指定时间（可配置）以内，则等待 2 倍的时间差后开始生成；若两者偏差大于某个设定的时间阈值（可配置），则立即抛出异常，避免阻塞。 **系统重启时**

jvmId 变化，基于 mac\\hostip\\jvmid 生成的机器 WorkerId 变化，即使在时钟回拨时也可以尽最大可能避免生成重复 id。

当然也可以借助第三方中间件实现时间回拨处理，比如算法运行时将 lastTimestamp 写入 redis，系统启动时读取 redis 存储的 lastTimestamp 值和当前时间比较。若当前时间戳 \<lastTimestamp，则启动失败。

#### 字符串位数补齐

正数的 Long 类型转换为 10 进制数范围：0~9,223,372,036,854,775,807，可见长度为最多 19 位，因此 SnowFlake 算法生成的 id 位数统一设定为 19 位为宜。

一般刚开始使用时为 18 位，但时间距离起始时间超过一定值后，会变为 19 位。

消耗完 18 位所需的时间：1\*10^18 / (3600 *24* 365 *1000* 2^22) ≈ 7.56 年，即时间差超过 7.56 年，就会达到 19 位。

因此我们设置初始时间 \< 当前时间 - 7.56 年，保证雪花算法生成的 id 位数统一为 19 位。

### 接口设计

#### 原始算法接口

使用者可以传入自行生成的 workerId、datacenterId，原汁原味的 SnowFlake。

#### 自动生成 workerId、datacenterId 接口

简化 SnowFlake 的使用，不保证 100%不重复，尽最大概率不重复。

#### 业务定制接口

调整雪花算法的 bit 位，即可以根据业务对 64 个 bit 位作出调整。

有的场景下我们需要定制雪花算法，比如生成 15 位的 10 进制数字。

生成 15 位十进制数字需要 53 位二进制数，除了 41 位时间戳 + 1 位符号位之外，还有 11 位可以用，可以采用 2 + 3 + 6（datacenterId + workerId + seqId）。

15 位的场景下理论支持单位毫秒 64 笔，每秒 64000 笔不重复，从中小规模业务量来看， tps>64000 的性能瓶颈短期不大可能出现。

#### 订单号生成

业务系统使用基于 snowflake 的 ID 生成器，比如拼接一些业务字段，比如生成订单号时传入 pid\\appId\\时间戳等。

### 算法实现

本文提供 Java 版的算法实现，欢迎评论区留言批评指正。

```java
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.lang.management.ManagementFactory;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.Date;
import java.util.concurrent.ThreadLocalRandom;
/**
 * @author NiaoGe
 * <p>
 * 雪花算法生成唯一 id,参考开源项目：
 * https://gitee.com/yu120/sequence
 * https://apidoc.gitee.com/loolly/hutool/cn/hutool/core/util/IdUtil.html
 * </p>
 */
public class IdGenerator {
    private static final Logger logger = LoggerFactory.getLogger(IdGenerator.class);
    //工作机器 id
    private long workerId;
    //数据中心 id
    private long datacenterId;
    //序列号
    private long sequence = 0L;
    //基准时间，一般取系统的最近时间（一旦确定不能变动）
    private long twepoch;
    private long workerIdBits;
    private long datacenterIdBits;
    private long maxWorkerId;
    private long maxDatacenterId;
    //毫秒内自增位数
    private long sequenceBits;
    //位与运算保证毫秒内 Id 范围
    private long sequenceMask;
    //工作机器 id 需要左移的位数
    private long workerIdShift;
    //数据中心 id 需要左移位数
    private long datacenterIdShift;
    //时间戳需要左移位数
    private long timestampLeftShift;
    //上次生成 id 的时间戳，初始值为负数
    private long lastTimestamp = -1L;
    //true 表示毫秒内初始序列采用随机值
    private boolean randomSequence;
    //随机初始序列计数器
    private long count = 0L;
    //允许时钟回拨的毫秒数
    private long timeOffset;
    private final ThreadLocalRandom tlr = ThreadLocalRandom.current();
    /**
     * 无参构造器，自动生成 workerId/datacenterId
     */
    public IdGenerator() {
        this(false, 10, null, 5L, 5L, 12L);
    }
    /**
     * 有参构造器,调用者自行保证数据中心 ID+机器 ID 的唯一性
     * 标准 snowflake 实现
     *
     * @param workerId     工作机器 ID
     * @param datacenterId 数据中心 ID
     */
    public IdGenerator(long workerId, long datacenterId) {
        this(workerId, datacenterId, false, 10, null, 5L, 5L, 12L);
    }
    /**
     * @param randomSequence   true 表示每毫秒内起始序号使用随机值
     * @param timeOffset       允许时间回拨的毫秒数
     * @param epochDate        基准时间
     * @param workerIdBits     workerId 位数
     * @param datacenterIdBits datacenterId 位数
     * @param sequenceBits     sequence 位数
     */
    public IdGenerator(boolean randomSequence, long timeOffset, Date epochDate, long workerIdBits, long datacenterIdBits, long sequenceBits) {
        if (null != epochDate) {
            this.twepoch = epochDate.getTime();
        } else {
            // 2012/12/12 23:59:59 GMT
            this.twepoch = 1355327999000L;
        }
        this.workerIdBits = workerIdBits;
        this.datacenterIdBits = datacenterIdBits;
        this.maxWorkerId = -1L ^ (-1L << workerIdBits);
        this.maxDatacenterId = -1L ^ (-1L << datacenterIdBits);
        this.sequenceBits = sequenceBits;
        this.sequenceMask = -1L ^ (-1L << sequenceBits);
        this.workerIdShift = sequenceBits;
        this.datacenterIdShift = sequenceBits + workerIdBits;
        this.timestampLeftShift = sequenceBits + workerIdBits + datacenterIdBits;
        this.datacenterId = getDatacenterId(maxDatacenterId);
        this.workerId = getMaxWorkerId(datacenterId, maxWorkerId);
        this.randomSequence = randomSequence;
        this.timeOffset = timeOffset;
        String initialInfo = String.format("worker starting. timestamp left shift %d, datacenter id bits %d, worker id bits %d, sequence bits %d, datacenterid  %d, workerid %d",
                timestampLeftShift, datacenterIdBits, workerIdBits, sequenceBits, datacenterId, workerId);
        logger.info(initialInfo);
    }
    /**
     * 自定义 workerId+datacenterId+其它初始配置
     * 调整 workerId、datacenterId、sequence 位数定制雪花算法,控制生成的 Id 的位数
     *
     * @param workerId         工作机器 ID
     * @param datacenterId     数据中心 ID
     * @param randomSequence   true 表示每毫秒内起始序号使用随机值
     * @param timeOffset       允许时间回拨的毫秒数
     * @param epochDate        基准时间
     * @param workerIdBits     workerId 位数
     * @param datacenterIdBits datacenterId 位数
     * @param sequenceBits     sequence 位数
     */
    public IdGenerator(long workerId, long datacenterId, boolean randomSequence, long timeOffset, Date epochDate, long workerIdBits, long datacenterIdBits, long sequenceBits) {
        this.workerIdBits = workerIdBits;
        this.datacenterIdBits = datacenterIdBits;
        this.maxWorkerId = -1L ^ (-1L << workerIdBits);
        this.maxDatacenterId = -1L ^ (-1L << datacenterIdBits);
        if (workerId > maxWorkerId || workerId < 0) {
            throw new IllegalArgumentException(String.format("worker Id can't be greater than %d or less than 0\r\n", maxWorkerId));
        }
        if (datacenterId > maxDatacenterId || datacenterId < 0) {
            throw new IllegalArgumentException(String.format("datacenter Id can't be greater than %d or less than 0\r\n", maxDatacenterId));
        }
        if (null != epochDate) {
            this.twepoch = epochDate.getTime();
        } else {
            // 2012/12/12 23:59:59 GMT
            this.twepoch = 1355327999000L;
        }
        this.sequenceBits = sequenceBits;
        this.sequenceMask = -1L ^ (-1L << sequenceBits);
        this.workerIdShift = sequenceBits;
        this.datacenterIdShift = sequenceBits + workerIdBits;
        this.timestampLeftShift = sequenceBits + workerIdBits + datacenterIdBits;
        this.workerId = workerId;
        this.datacenterId = datacenterId;
        this.timeOffset = timeOffset;
        this.randomSequence = randomSequence;
        String initialInfo = String.format("worker starting. timestamp left shift %d, datacenter id bits %d, worker id bits %d, sequence bits %d, datacenterid  %d, workerid %d",
                timestampLeftShift, datacenterIdBits, workerIdBits, sequenceBits, datacenterId, workerId);
        logger.info(initialInfo);
    }
    private static long getDatacenterId(long maxDatacenterId) {
        long id = 0L;
        try {
            InetAddress ip = InetAddress.getLocalHost();
            NetworkInterface network = NetworkInterface.getByInetAddress(ip);
            if (network == null) {
                id = 1L;
            } else {
                byte[] mac = network.getHardwareAddress();
                if (null != mac) {
                    id = ((0x000000FF & (long) mac[mac.length - 1]) | (0x0000FF00 & (((long) mac[mac.length - 2]) << 8))) >> 6;
                    id = id % (maxDatacenterId + 1);
                }
            }
        } catch (Exception e) {
            throw new RuntimeException("GetDatacenterId Exception", e);
        }
        return id;
    }
    private static long getMaxWorkerId(long datacenterId, long maxWorkerId) {
        StringBuilder macIpPid = new StringBuilder();
        macIpPid.append(datacenterId);
        try {
            String name = ManagementFactory.getRuntimeMXBean().getName();
            if (name != null && !name.isEmpty()) {
                //GET jvmPid
                macIpPid.append(name.split("@")[0]);
            }
            //GET hostIpAddress
            String hostIp = InetAddress.getLocalHost().getHostAddress();
            String ipStr = hostIp.replaceAll("\\.", "");
            macIpPid.append(ipStr);
        } catch (Exception e) {
            throw new RuntimeException("GetMaxWorkerId Exception", e);
        }
        //MAC + PID + IP 的 hashcode 取低 16 位
        return (macIpPid.toString().hashCode() & 0xffff) % (maxWorkerId + 1);
    }
    public synchronized long nextId() {
        long currentTimestamp = timeGen();
        //获取当前时间戳如果小于上次时间戳，则表示时间戳获取出现异常
        if (currentTimestamp < lastTimestamp) {
            // 校验时间偏移回拨量
            long offset = lastTimestamp - currentTimestamp;
            if (offset > timeOffset) {
                throw new RuntimeException("Clock moved backwards, refusing to generate id for [" + offset + "ms]");
            }
            try {
                // 时间回退 timeOffset 毫秒内，则允许等待 2 倍的偏移量后重新获取，解决小范围的时间回拨问题
                this.wait(offset << 1);
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
            currentTimestamp = timeGen();
            if (currentTimestamp < lastTimestamp) {
                throw new RuntimeException("Clock moved backwards, refusing to generate id for [" + offset + "ms]");
            }
        }
        //如果获取的当前时间戳等于上次时间戳（即同一毫秒内），则序列号自增
        if (lastTimestamp == currentTimestamp) {
            // randomSequence 为 true 表示随机生成允许范围内的起始序列,否则毫秒内起始值从 0L 开始自增
            long tempSequence = sequence + 1;
            if (randomSequence) {
                sequence = tempSequence & sequenceMask;
                count = (count + 1) & sequenceMask;
                if (count == 0) {
                    currentTimestamp = this.tillNextMillis(lastTimestamp);
                }
            } else {
                sequence = tempSequence & sequenceMask;
                if (sequence == 0) {
                    currentTimestamp = this.tillNextMillis(lastTimestamp);
                }
            }
        } else {
            sequence = randomSequence ? tlr.nextLong(sequenceMask + 1) : 0L;
            count = 0L;
        }
        lastTimestamp = currentTimestamp;
        return ((currentTimestamp - twepoch) << timestampLeftShift) |
                (datacenterId << datacenterIdShift) |
                (workerId << workerIdShift) |
                sequence;
    }
    private long tillNextMillis(long lastTimestamp) {
        long timestamp = timeGen();
        while (timestamp <= lastTimestamp) {
            timestamp = timeGen();
        }
        return timestamp;
    }
    private long timeGen() {
        return System.currentTimeMillis();
    }
    /**
     * 测试
     * @param args
     */
    public static void main(String[] args) {
//        for (int i = 0; i < 10; i++) {
//            IdGenerator idGenerator = new IdGenerator();
//            new Thread(() -> {
//                for (int j = 0; j < 100; j++) {
//                    System.out.println(idGenerator.nextId());
//                }
//            }).start();
//        }
//        IdGenerator idGenerator = new IdGenerator(1, 1);
//        for (int j = 0; j < 2000; j++) {
//            System.out.println(System.currentTimeMillis() + " " + idGenerator.nextId());
//        }
//        IdGenerator idGenerator = new IdGenerator(true, 10, null, 3L, 2L, 7L);
//        for (int j = 0; j < 2000; j++) {
//            System.out.println(System.currentTimeMillis() + " " + idGenerator.nextId());
//        }
        IdGenerator shortIdGenerator = new IdGenerator(7, 3, true, 10, null, 3, 2, 7);
        for (int j = 0; j < 1000; j++) {
            System.out.println(System.currentTimeMillis() + " " + shortIdGenerator.nextId());
        }
    }
}
```

订单号生成案例

```java
import java.text.SimpleDateFormat;
import java.util.Date;
/**
 * 使用 IdGenerator 生成唯一订单号
 */
public class OrderNoGenerator {
    private IdGenerator idGenerator;
    /**
     * 无参构造器，自动生成 workerId/datacenterId
     */
    public OrderNoGenerator() {
        this.idGenerator = new IdGenerator();
    }
    /**
     * 有参构造器,使用者自行保证数据中心 ID+机器 ID 的唯一性
     *
     * @param idGenerator
     */
    public OrderNoGenerator(IdGenerator idGenerator) {
        this.idGenerator = idGenerator;
    }
    /**
     * 生成订单号
     * @param env        1=dev,2=sit,3=uat,4=prd
     * @param pid        1=产品线 1,2=产品线 2,3=产品线 3
     * @param dateFormat 日期格式
     * @return
     */
    public String getOrderNo(String env, String pid,  String dateFormat) {
        if (dateFormat == null || dateFormat.isEmpty()) {
            dateFormat = "yyMMddHH";
        }
        String dateStr = new SimpleDateFormat(dateFormat).format(new Date());
        return env + pid + dateStr + idGenerator.nextId();
    }
    /**
     * 测试
     *
     * @param args
     */
    public static void main(String[] args) {
        OrderNoGenerator orderNoGenerator = new OrderNoGenerator();
        for (int i = 0; i < 1000; i++) {
            System.out.println(System.currentTimeMillis() + " " + orderNoGenerator.getOrderNo("3", "1",  null));
        }
        System.out.println("-------------------------------------------------");
        //雪花算法生成 15 位 ID
        IdGenerator shortIdGenerator = new IdGenerator(1, 2, false, 10, null, 3L, 2L, 7L);
        OrderNoGenerator shortOrderNoGenerator = new OrderNoGenerator(shortIdGenerator);
        for (int i = 0; i < 1000; i++) {
            System.out.println(System.currentTimeMillis() + " " + shortOrderNoGenerator.getOrderNo("3", "1",  null));
        }
    }
}
```

