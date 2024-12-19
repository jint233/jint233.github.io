# Java 中的 ThreadLocal

## 前言

面试的时候被问到 ThreadLocal 的相关知识，没有回答好（奶奶的，现在感觉问啥都能被问倒），所以我决定先解决这几次面试中都遇到的高频问题，把这几个硬骨头都能理解的透彻的说出来了，感觉最起码不能总是一轮游。

## ThreadLocal 介绍

ThreadLocal 是 JDK1.2 开始就提供的一个用来存储线程本地变量的类。ThreadLocal 中的变量是在每个线程中独立存在的，当多个线程访问 ThreadLocal 中的变量的时候，其实都是访问的自己当前线程的内存中的变量，从而保证的变量的线程安全。

我们一般在使用 ThreadLocal 的时候都是为了解决线程中存在的变量竞争问题。其实解决这类问题，通常大家也会想到使用 synchronized 来加锁解决。

例如在解决 SimpleDateFormat 的线程安全的时候。SimpleDateFormat 是非线程安全的，它里面无论的是 format () 方法还是 parse () 方法，都有使用它自己内部的一个 Calendar 类的对象，format 方法是设置时间，parse () 方法里面是先调用 Calendar 的 clear () 方法，然后又调用了 Calendar 的 set () 方法（赋值），如果一个线程刚调用了 set () 进行赋值，这个时候又来了一个线程直接调用了 clear () 方法，那么这个 parse () 方法执行的结果就会有问题的。

- **解决办法一**

    将使用 SimpleDateformat 的方法加上 synchronized，这样虽然保证了线程安全，但却降低了效率，同一时间只有一个线程能使用格式化时间的方法。

    ```java
    private static SimpleDateFormat simpleDateFormat = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
    public static synchronized String formatDate(Date date){
        return simpleDateFormat.format(date);
    }
    ```

- **解决办法二**

    将 SimpleDateFormat 的对象，放到 ThreadLocal 里面，这样每个线程中都有一个自己的格式对象的副本了。互不干扰，从而保证了线程安全。

    ```java
    private static final ThreadLocal<SimpleDateFormat> simpleDateFormatThreadLocal = ThreadLocal.withInitial(() -> new SimpleDateFormat("yyyy-MM-dd HH:mm:ss"));
    public static String formatDate(Date date){
    return simpleDateFormatThreadLocal.get().format(date);
    }
    ```

## ThreadLocal 的原理

我们先看一下 ThreadLocal 是怎么使用的。

```java
ThreadLocal<Integer> threadLocal99 = new ThreadLocal<Integer>();
threadLocal99.set(3);
int num = threadLocal99.get();
System.out.println ("数字:"+num);
threadLocal99.remove();
System.out.println ("数字 Empty:"+threadLocal99.get ());
```

运行结果：

```bash
数字：3
数字 Empty:null
```

使用起来很简单，主要是将变量放到 ThreadLocal 里面，在线程执行过程中就可以取到，当执行完成后在 remove 掉就可以了，只要没有调用 remove () 当前线程在执行过程中都是可以拿到变量数据的。 因为是放到了当前执行的线程中，所以 ThreadLocal 中的变量值只能当前线程来使用，从而保证的了线程安全（当前线程的子线程其实也是可以获取到的）。

来看一下 ThreadLocal 的 set () 方法源码

```java
public void set(T value) {
   // 获取当前线程
   Thread t = Thread.currentThread();
   // 获取 ThreadLocalMap
   ThreadLocal.ThreadLocalMap map = getMap(t);
   // ThreadLocalMap 对象是否为空，不为空则直接将数据放入到 ThreadLocalMap 中
   if (map != null)
       map.set(this, value);
   else
       createMap (t, value); // ThreadLocalMap 对象为空，则先创建对象，再赋值。
}
```

我们看到变量都是存放在了 ThreadLocalMap 这个变量中的。那么 ThreadLocalMap 又是怎么来的呢？

```java
ThreadLocalMap getMap(Thread t) {
    return t.threadLocals;
}
public class Thread implements Runnable {
 ... ...
 /* ThreadLocal values pertaining to this thread. This map is maintained
     * by the ThreadLocal class. */
    ThreadLocal.ThreadLocalMap threadLocals = null;
    ... ...
}
```

通过上面的源码，我们发现 ThreadLocalMap 变量是当前执行线程中的一个变量，所以说，ThreadLocal 中存放的数据其实都是放到了当前执行线程中的一个变量里面了。也就是存储在了当前的线程对象里了，别的线程里面是另一个线程对象了，拿不到其他线程对象中的数据，所以数据自然就隔离开了。

### 那么 ThreadLocalMap 是怎么存储数据的呢？

ThreadLocalMap 是 ThreadLocal 类里的一个内部类，虽然类的名字上带着 Map 但却没有实现 Map 接口，只是结构和 Map 类似而已。

<figure markdown="span">
<img src="../../assets/20200909231451433.png" alt="img">
</figure>

ThreadLocalMap 内部其实是一个 Entry 数组，Entry 是 ThreadLocalMap 中的一个内部类，继承自 WeakReference，并将 ThreadLocal 类型的对象设置为了 Entry 的 Key，以及对 Key 设置成弱引用。 ThreadLocalMap 的内部数据结构，就大概是这样的 key,value 组成的 Entry 的数组集合。

<figure markdown="span">
<img src="../../assets/2020090923454535.png" alt="img">
</figure>

和真正的 Map 还是有区别的，没有链表了，这样在解决 key 的 hash 冲突的时候措施肯定就和 HashMap 不一样了。一个线程中是可以创建多个 ThreadLocal 对象的，多个 ThreadLocal 对象就会存放多个数据，那么在 ThreadLocalMap 中就会以数组的形式存放这些数据。

我们来看一下具体的 ThreadLocalMap 的 set () 方法的源码

```java
/**
 * Set the value associated with key.
 * @param key the thread local object
 * @param value the value to be set
 */
private void set(ThreadLocal<?> key, Object value) {
    // We don't use a fast path as with get() because it is at
    // least as common to use set() to create new entries as
    // it is to replace existing ones, in which case, a fast
    // path would fail more often than not.
    Entry[] tab = table;
    int len = tab.length;
    // 定位在数组中的位置
    int i = key.threadLocalHashCode & (len-1);
    for (Entry e = tab[i];
         e != null;
         e = tab[i = nextIndex(i, len)]) {
        ThreadLocal<?> k = e.get();
        // 如果当前位置不为空，并且当前位置的 key 和传过来的 key 相等，那么就会覆盖当前位置的数据
        if (k == key) {
            e.value = value;
            return;
        }
        // 如果当前位置为空，则初始化一个 Entry 对象，放到当前位置。
        if (k == null) {
            replaceStaleEntry(key, value, i);
            return;
        }
    }
    // 如果当前位置不为空，并且当前位置的 key 也不等于要赋值的 key ，那么将去找下一个空位置，直接将数据放到下一个空位置处。
    tab[i] = new Entry(key, value);
    int sz = ++size;
    if (!cleanSomeSlots(i, sz) && sz >= threshold)
        rehash();
}
```

我们从 set () 方法中可以看到，处理逻辑有四步。

- 第一步先根据 Threadlocal 对象的 hashcode 和数组长度做与运算获取数据应该放在当前数组中的位置。
- 第二步就是判断当前位置是否为空，为空的话就直接初始化一个 Entry 对象，放到当前位置。
- 第三步如果当前位置不为空，而当前位置的 Entry 中的 key 和传过来的 key 一样，那么直接覆盖掉当前位置的数据。
- 第四步如果当前位置不为空，并且当前位置的 Entry 中的 key 和传过来的 key 也不一样，那么就会去找下一个空位置，然后将数据存放到空位置（ **数组超过长度后，会执行扩容的** ）；

在 get 的时候也是类似的逻辑，先通过传入的 ThreadLocal 的 hashcode 获取在 Entry 数组中的位置，然后拿当前位置的 Entry 的 Key 和传入的 ThreadLocal 对比，相等的话，直接把数据返回，如果不相等就去判断和数组中的下一个值的 key 是否相等。。。

```java
private Entry getEntry(ThreadLocal<?> key) {
    int i = key.threadLocalHashCode & (table.length - 1);
    Entry e = table[i];
    if (e != null && e.get() == key)
        return e;
    else
        return getEntryAfterMiss(key, i, e);
}
/**
 * Version of getEntry method for use when key is not found in
 * its direct hash slot.
 *
 * @param  key the thread local object
 * @param  i the table index for key's hash code
 * @param  e the entry at table[i]
 * @return the entry associated with key, or null if no such
 */
private Entry getEntryAfterMiss(ThreadLocal<?> key, int i, Entry e) {
    Entry[] tab = table;
    int len = tab.length;
    while (e != null) {
        ThreadLocal<?> k = e.get();
        if (k == key)
            return e;
        if (k == null)
            expungeStaleEntry(i);
        else
            i = nextIndex(i, len);
        e = tab[i];
    }
    return null;
}
```

我们上文一直说，ThreadLocal 是保存在单个线程中的数据，每个线程都有自己的数据，但是实际 ThreadLocal 里面的真正的对象数据，其实是保存在堆里面的，而线程里面只是存储了对象的引用而已。并且我们在使用的时候通常需要在上一个线程执行的方法的上下文共享 ThreadLocal 中的变量。例如我的主线程是在某个方法中执行代码呢，但是这个方法中有一段代码时新创建了一个线程，在这个线程里面还使用了我这个正在执行的方法里面的定义的 ThreadLocal 里面的变量。

这个时候，就是需要从新线程里面调用外面线程的数据，这个就需要线程间共享了。这种子父线程共享数据的情况，ThreadLocal 也是支持的。 例如：

```java
 ThreadLocal threadLocalMain = new InheritableThreadLocal();
 threadLocalMain.set ("主线程变量");
 Thread t = new Thread() {
     @Override
     public void run() {
         super.run();
         System.out.println ("现在获取的变量是 =" + threadLocalMain.get ());
     }
 };
 t.start();
```

运行结果：

```bash
现在获取的变量是 = 主线程变量
```

上面这样的代码就能实现子父线程共享数据的情况，重点是使用 InheritableThreadLocal 来实现的共享。 那么它是怎么实现数据共享的呢？ 在 Thread 类的 init () 方法中有这么一段代码：

```java
if (inheritThreadLocals && parent.inheritableThreadLocals != null)
            this.inheritableThreadLocals =ThreadLocal.createInheritedMap(parent.inheritableThreadLocals);
```

这段代码的意思是，在创建线程的时候，如果当前线程的 inheritThreadLocals 变量和父线程的 inheritThreadLocals 变量都不为空的时候，会将父线程的 inheritThreadLocals 变量中的数据，赋给当前线程中的 inheritThreadLocals 变量。

## ThreadLocal 的内存泄漏问题

上文我们也提到过，ThreadLocal 中的 ThreadLocalMap 里面的 Entry 对象是继承自 WeakReference 类的，说明 Entry 的 key 是一个弱引用。

<figure markdown="span">
<img src="../../assets/20200910083829900.png" alt="img">
</figure>

!!! Note "弱引用"
    弱引用是用来描述那些非必须的对象，弱引用的对象，只能生存到下一次垃圾收集发生为止。当垃圾收集器开始工作，无论当前内存是否足够，都会回收掉只被弱引用关联的对象。

**这个弱引用还是 ThreadLocal 对象本身，所以一般在线程执行完成后，ThreadLocal 对象就会变成 null 了，而为 null 的弱引用对象，在下一次 GC 的时候就会被清除掉，这样 Entry 的 Key 的内存空间就被释放出来了，但是 Entry 的 value 还在占用的内存，如果线程是被复用的（例如线程池中的线程），后面也不使用 Th      readLocal 存取数据了，那么这里面的 value 值会一直存在，最终就导致了内存泄漏。**  

**防止内存泄漏的办法就是在每次使用完 ThreadLocal 的时候都去执行以下 remove()方法，就可以把 key 和 value 的空间都释放了。**

### 那既然容易产生内存泄漏，为什么还要设置成弱引用的呢？

如果正常情况下应该是强引用，但是强引用只要引用关系还在就一直不会被回收，所以如果线程被复用了，那么 Entry 中的 Key 和 Value 都不会被回收，这样就造成了 Key 和 Value 都会发生内存泄漏了；

但是设置成弱引用，当 ThreadLocal 对象，没有被强引用后，就会被回收，回收后，Entry 中的 key 就会被设置成 null 了，如果 Thread 被重复使用，只要还会用 ThreadLocal 存储数据，那么就会调用 ThreadLocal 的，set、get 等方法，在调用 set、get、等方法的时候，是会扫描 Entry 中 key 为 null 的数据的。

当发现 Entry 中，有 key 为 null 的数据时，会将 value 也设置为 null，这样就将 value 的值也进行了回收，能进一步防止内存泄漏了，并且在进行 rehash 的时候，也是先清除掉 key 是 null 的数据后，如果空间还不够，才进行扩容的。

但是虽然将 key 设置了弱引用，但是如果一个线程被重复利用，执行完任务后，再也不使用 ThreadLocal 了，那么最后 value 值会一直存在，最终也是会导致内存泄漏的，所以使用 ThreadLocal 的时候，最后一定要执行 remove () 方法。
