# MySQL · 引擎特性 · InnoDB 同步机制

## 前言

现代操作系统以及硬件基本都支持并发程序，而在并发程序设计中，各个进程或者线程需要对公共变量的访问加以制约，此外，不同的进程或者线程需要协同工作以完成特征的任务，这就需要一套完善的同步机制，在 Linux 内核中有相应的技术实现，包括原子操作，信号量，互斥锁，自旋锁，读写锁等。InnoDB 考虑到效率和监控两方面的原因，实现了一套独有的同步机制，提供给其他模块调用。本文的分析默认基于 MySQL 5.6，CentOS 6，gcc 4.8，其他版本的信息会另行指出。

## 基础知识

同步机制对于其他数据库模块来说相对独立，但是需要比较多的操作系统以及硬件知识，这里简单介绍一下几个有用的概念，便于读者理解后续概念。**内存模型 :** 主要分为语言级别的内存模型和硬件级别的内存模型。语言级别的内存模型，C/C++属于 weak memory model，简单的说就是编译器在进行编译优化的时候，可以对指令进行重排，只需要保证在单线程的环境下，优化前和优化后执行结果一致即可，执行中间过程不保证跟代码的语义顺序一致。所以在多线程的环境下，如果依赖代码中间过程的执行顺序，程序就会出现问题。硬件级别的内存模型，我们常用的 cpu，也属于弱内存模型，即 cpu 在执行指令的时候，为了提升执行效率，也会对某些执行进行乱序执行（按照 wiki 提供的资料，在 x86 64 环境下，只会发生读写乱序，即读操作可能会被乱序到写操作之前），如果在编程的时候不做一些措施，同样容易造成错误。***内存屏障 :** \*为了解决弱内存模型造成的问题，需要一种能控制指令重排或者乱序执行程序的手段，这种技术就叫做内存屏障，程序员只需要在代码中插入特定的函数，就能控制弱内存模型带来的负面影响，当然，由于影响了乱序和重排这类的优化，对代码的执行效率有一定的影响。具体实现上，内存屏障技术分三种，一种是 full memory barrier，即 barrier 之前的操作不能乱序或重排到 barrier 之后，同时 barrier 之后的操作不能乱序或重排到 barrier 之前，当然这种 full barrier 对性能影响最大，为了提高效率才有了另外两种：acquire barrier 和 release barrier，前者只保证 barrier 后面的操作不能移到之前，后者只保证 barrier 前面的操作不移到之后。***互斥锁 :** \*互斥锁有两层语义，除了大家都知道的排他性（即只允许一个线程同时访问）外，还有一层内存屏障（full memory barrier）的语义，即保证临界区的操作不会被乱序到临界区外。Pthread 库里面常用的 mutex，conditional variable 等操作都自带内存屏障这层语义。此外，使用 pthread 库，每次调用都需要应用程序从用户态陷入到内核态中查看当前环境，在锁冲突不是很严重的情况下，效率相对比较低。***自旋锁 :** \*传统的互斥锁，只要一检测到锁被其他线程所占用了，就立刻放弃 cpu 时间片，把 cpu 留给其他线程，这就会产生一次上下文切换。当系统压力大的时候，频繁的上下文切换会导致 sys 值过高。自旋锁，在检测到锁不可用的时候，首先 cpu 忙等一小会儿，如果还是发现不可用，再放弃 cpu，进行切换。互斥锁消耗 cpu sys 值，自旋锁消耗 cpu usr 值。***递归锁 :** \*如果在同一个线程中，对同一个互斥锁连续加锁两次，即第一次加锁后，没有释放，继续进行对这个锁进行加锁，那么如果这个互斥锁不是递归锁，将导致死锁。可以把递归锁理解为一种特殊的互斥锁。***死锁 :** \*构成死锁有四大条件，其中有一个就是加锁顺序不一致，如果能保证不同类型的锁按照某个特定的顺序加锁，就能大大降低死锁发生的概率，之所以不能完全消除，是因为同一种类型的锁依然可能发生死锁。另外，对同一个锁连续加锁两次，如果是非递归锁，也将导致死锁。

## 原子操作

现代的 cpu 提供了对单一变量简单操作的原子指令，即这个变量的这些简单操作只需要一条 cpu 指令即可完成，这样就不用对这个操作加互斥锁了，在锁冲突不激烈的情况下，减少了用户态和内核态的切换，化悲观锁为乐观锁，从而提高了效率。此外，现在外面很火的所谓无锁编程（类似 CAS 操作），底层就是用了这些原子操作。gcc 为了方便程序员使用这些 cpu 原子操作，提供了一系列__sync 开头的函数，这些函数如果包含内存屏障语义，则同时禁止编译器指令重排和 cpu 乱序执行。 InnoDB 针对不同的操作系统以及编译器环境，自己封装了一套原子操作，在头文件 os0sync.h 中。下面的操作基于 Linux x86 64 位环境， gcc 4.1 以上的版本进行分析。 `os_compare_and_swap_xxx(ptr, old_val, new_val)`类型的操作底层都使用了 gcc 包装的`__sync_bool_compare_and_swap(ptr, old_val, new_val)`函数，语义为，交换成功则返回 true，ptr 是交换后的值，old_val 是之前的值，new_val 是交换后的预期值。这个原子操作是个内存屏障（full memory barrier）。 `os_atomic_increment_xxx`类型的操作底层使用了函数`__sync_add_and_fetch`，`os_atomic_decrement_xxx`类型的操作使用了函数`__sync_sub_and_fetch`，分别表示原子递增和原子递减。这个两个原子操作也都是内存屏障（full memory barrier）。 另外一个比较重要的原子操作是`os_atomic_test_and_set_byte(ptr, new_val)`，这个操作使用了`__sync_lock_test_and_set(ptr, new_val)`这个函数，语义为，把 ptr 设置为 new_val，同时返回旧的值。这个操作提供了原子改变某个变量值的操作，InnoDB 锁实现的同步机制中，大量的用了这个操作，因此比较重要。需要注意的是，参看 gcc 文档，这个操作不是 full memory barrier，只是一个 acquire barrier，简单的说就是，代码中`__sync_lock_test_and_set`之后操作不能被乱序或者重排到`__sync_lock_test_and_set`之前，但是`__sync_lock_test_and_set`之前的操作可能被重排到其之后。 关于内存屏障的专门指令，MySQL 5.7 提供的比较完善。`os_rmb`表示 acquire barrier，`os_wmb`表示 release barrier。如果在编程时，需要在某个位置准确的读取一个变量的值时，记得在读取之前加上 os_rmb，同理，如果需要在某个位置保证一个变量已经被写了，记得在写之后调用 os_wmb。

## 条件通知机制

条件通知机制在多线程协作中非常有用，一个线程往往需要等待其他线程完成指定工作后，再进行工作，这个时候就需要有线程等待和线程通知机制。`Pthread_cond_XXX`类似的变量和函数来完成等待和通知的工作。InnoDB 中，对 Pthread 库进行了简单的封装，并在此基础上，进一步抽象，提供了一套方便易用的接口函数给调用者使用。

### 系统条件变量

在文件 os0sync.cc 中，`os_cond_XXX`类似的函数就是 InnoDB 对 Pthread 库的封装。常用的几个函数如： `os_cond_t`是核心的操作对象，其实就是 pthread_cond_t 的一层 typedef 而已，`os_cond_init`初始化函数，`os_cond_destroy`销毁函数，`os_cond_wait`条件等待，不会超时，`os_cond_wait_timed`条件等待，如果超时则返回，`os_cond_broadcast`唤醒所有等待线程，`os_cond_signal`只唤醒其中一个等待线程，但是在阅读源码的时候发现，似乎没有什么地方调用了`os_cond_signal`。。。 此外，还有一个`os_cond_module_init`函数，用来 window 下的初始化操作。 在 InnoDB 下，`os_cond_XXX`模块的函数主要是给 InnoDB 自己设计的条件变量使用。

### InnoDB 条件变量

如果在 InnoDB 层直接使用系统条件变量的话，主要有四个弊端，首先，弊端 1，系统条件变量的使用需要与一个系统互斥锁（详见下一节）相配合使用，使用完还要记得及时释放，使用者会比较麻烦。接着，弊端 2，在条件等待的时候，需要在一个循环中等待，使用者还是比较麻烦。最后，弊端 3，也是比较重要的，不方便系统监控。 基于以上几点，InnoDB 基于系统的条件变量和系统互斥锁自己实现了一套条件通知机制。主要在文件 os0sync.cc 中实现，相关数据结构以及接口进一层的包装在头文件 os0sync.h 中。使用方法如下： InnoDB 条件变量核心数据结构为`os_event_t`，类似`pthread_cont_t`。如果需要创建和销毁则分别使用`os_event_create`和`os_event_free`函数。需要等待某个条件变量，先调用`os_event_reset`（原因见下一段），然后使用`os_event_wait`，如果需要超时等待，使用`os_event_wait_time`替换`os_event_wait`即可，`os_event_wait_XXX`这两个函数，解决了弊端 1 和弊端 2，此外，建议把`os_event_reset`返回值传给他们，这样能防止多线程情况下的无限等待（详见下下段）。如果需要发出一个条件通知，使用`os_event_set`。这个几个函数，里面都插入了一些监控信息，方便 InnoDB 上层管理。怎么样，方便多了吧~

#### 多线程环境下可能发生的问题

首先来说说两个线程下会发生的问题。创建后，正常的使用顺序是这样的，线程 A 首先`os_event_reset`（步骤 1），然后`os_event_wait`（步骤 2），接着线程 B 做完该做的事情后，执行`os_event_set`（步骤 3）发送信号，通知线程 A 停止等待，但是在多线程的环境中，会出现以下两种步骤顺序错乱的情况：乱序 A： `步骤1--步骤3--步骤2`，乱序 B: `步骤3--步骤1--步骤2`。对于乱序 B，属于条件通知在条件等待之前发生，目前 InnoDB 条件变量的机制下，会发生无限等待，所以上层调用的时候一定要注意，例如在 InnoDB 在实现互斥锁和读写锁的时候为了防止发生条件通知在条件等待之前发生，在等待之前对 lock_word 再次进行了判断，详见 InnoDB 自旋互斥锁这一节。为了解决乱序 A，InnoDB 在核心数据结构 os_event 中引入布尔型变量 is_set，is_set 这个变量就表示是否已经发生过条件通知，在每次调用条件通知之前，会把这个变量设置为 true（在`os_event_reset`时改为 false，便于多次通知），在条件等待之前会检查一下这变量，如果这个变量为 true，就不再等待了。所以，乱序 A 也能保证不会发生无限等待。 接着我们来说说大于两个线程下可能会发生的问题。线程 A 和 C 是等待线程，等待同一个条件变量，B 是通知线程，通知 A 和 C 结束等待。考虑一个乱序 C：线程 A 执行`os_event_reset`（步骤 1），线程 B 马上就执行`os_event_set`（步骤 2）了，接着线程 C 执行了`os_event_reset`（步骤 3），最后线程 A 执行`os_event_wait`（步骤 4），线程 C 执行`os_event_wait`（步骤 5）。乍一眼看，好像看不出啥问题，但是实际上你会发现 A 和 C 线程在无限等待了。原因是，步骤 2，把 is_set 这个变量设置为 false，但是在步骤 3，线程 C 通过 reset 又把它给重新设回 false 了。。然后线程 A 和 C 在`os_event_wait`中误以为还没有发生过条件通知，就开始无限等待了。为了解决这个问题，InnoDB 在核心数据结构 os_event 中引入 64 位整形变量 signal_count，用来记录已经发出条件信号的次数。每次发出一个条件通知，这个变量就递增 1。`os_event_reset`的返回值就把当前的 signal_count 值取出来。`os_event_wait`如果发现有这个参数的传入，就会判断传入的参数与当前的 signal_count 值是否相同，如果不相同，表示这个已经通知过了，就不会进入等待了。举个例子，假设乱序 C，一开始的 signal_count 为 100，步骤 1 把这个参数传给了步骤 4，在步骤 4 中，`os_event_wait`会发现传入值 100 与当前的值 101（步骤 2 中递增了 1）不同，所以线程 A 认为信号已经发生过了，就不会再等待了。。。然而。。线程 C 呢？步骤 3 返回的值应该是 101，传给步骤 5 后，发生于当前值一样。。继续等待。。。仔细分析可以发现，线程 C 是属于条件变量通知发生在等待之前（步骤 2，步骤 3，步骤 5），上一段已经说过了，针对这种通知提前发出的，目前 InnoDB 没有非常好的解法，只能调用者自己控制。 总结一下， InnoDB 条件变量能方便 InnoDB 上层做监控，也简化了条件变量使用的方法，但是调用者上层逻辑必须保证条件通知不能过早的发出，否则就会有无限等待的可能。

## 互斥锁

互斥锁保证一段程序同时只能一个线程访问，保证临界区得到正确的序列化访问。同条件变量一样，InnoDB 对 Pthread 的 mutex 简单包装了一下，提供给其他模块用（主要是辅助其他自己实现的数据结构，不用 InnoDB 自己的互斥锁是为了防止递归引用，详见辅助结构这一节）。但与条件变量不同的是，InnoDB 自己实现的一套互斥锁并没有依赖 Pthread 库，而是依赖上述的原子操作（如果平台不支持原子操作则使用 Pthread 库，但是这种情况不太会发生，因为 gcc 在 4.1 就支持原子操作了）和上述的 InnoDB 条件变量。

### 系统互斥锁

相比与系统条件变量，系统互斥锁除了包装 Pthread 库外，还做了一层简单的监控统计，结构名为`os_mutex_t`。在文件 os0sync.cc 中，`os_mutex_create`创建 mutex，并调用`os_fast_mutex_init_func`创建 pthread 的 mutex，值得一提的是，创建 pthread mutex 的参数是`my_fast_mutexattr`的东西，其在 MySQL server 层函数`my_thread_global_init`初始化 ，只要 pthread 库支持，则默认成初始化为 PTHREAD_MUTEX_ADAPTIVE_NP 和 PTHREAD_MUTEX_ERRORCHECK。前者表示，当锁释放，之前在等待的锁进行公平的竞争，而不是按照默认的优先级模式。后者表示，如果发生了递归的加锁，即同一个线程对同一个锁连续加锁两次，第二次加锁会报错。另外三个有用的函数为，销毁锁`os_mutex_free`，加锁`os_mutex_enter`，解锁`os_mutex_exit`。 一般来说，InnoDB 上层模块不需要直接与系统互斥锁打交道，需要用锁的时候一般用 InnoDB 自己实现的一套互斥锁。系统互斥锁主要是用来辅助实现一些数据结构，例如最后一节提到的一些辅助结构，由于这些辅助结构可能本身就要提供给 InnoDB 自旋互斥锁用，为了防止递归引用，就暂时用系统互斥锁来代替。

### InnoDB 自旋互斥锁

为什么 InnoDB 需要实现自己的一套互斥锁，不直接用上述的系统互斥锁呢？这个主要有以下几个原因，首先，系统互斥锁是基于 pthread mutex 的，Heikki Tuuri（同步模块的作者，也是 Innobase 的创始人）认为在当时的年代 pthread mutex 上下文切换造成的 cpu 开销太大，使用 spin lock 的方式在多处理器的机器上更加有效，尤其是在锁竞争不是很严重的时候，Heikki Tuuri 还总结出，在 spin lock 大概自旋 20 微秒的时候在多处理的机器下效率最高。其次，不使用 pthread spin lock 的原因是，当时在 1995 年左右的时候，spin lock 的类似实现，效率很低，而且当时的 spin lock 不支持自定义自旋时间，要知道自旋锁在单处理器的机器上没什么卵用。最后，也是为了更加完善的监控需求。总的来说，有历史原因，有监控需求也有自定义自旋时间的需求，然后就有了这一套 InnoDB 自旋互斥锁。 InnoDB 自旋互斥锁的实现主要在文件 sync0sync.cc 和 sync0sync.ic 中，头文件 sync0sync.h 定义了核心数据结构 ib_mutex_t。使用方法很简单，`mutex_create`创建锁，`mutex_free`释放锁，`mutex_enter`尝试获得锁，如果已经被占用了，则等待。`mutex_exit`释放锁，同时唤醒所有等待的线程，拿到锁的线程开始执行，其余线程继续等待。`mutex_enter_nowait`这个函数类似 pthread 的 trylock，只要已检测到锁不用，就直接返回错误，不进行自旋等待。总体来说，InnoDB 自旋互斥锁的用法和语义跟系统互斥锁一模一样，但是底层实现却大相径庭。 在 ib_mutex_t 这个核心数据结构中，最重要的是前面两个变量：event 和 lock_word。lock_word 为 0 表示锁空闲，1 表示锁被占用，InnoDB 自旋互斥锁使用`__sync_lock_test_and_set`这个函数对 lock_word 进行原子操作，加锁的时候，尝试把其设置为 1，函数返回值不指示是否成功，指示的是尝试设置之前的值，因此如果返回值是 0，表示加锁成功，返回是 1 表示失败。如果加锁失败，则会自旋一段时间，然后等待在条件变量 event（`os_event_wait`）上，当锁占用者释放锁的时候，会使用`os_event_set`来唤醒所有的等待者。简单的来说，byte 类型的 lock_word 基于平台提供的原子操作来实现互斥访问，而 event 是 InnoDB 条件变量类型，用来实现锁释放后唤醒等待线程的操作。 接下来，详细介绍一下，`mutex_enter`和`mutex_exit`的逻辑，InnoDB 自旋互斥锁的精华都在这两个函数中。 mutex_enter 的伪代码如下：

```python
if (__sync_lock_test_and_set(mutex->lock_word, 1) == 0) {
    get mutex successfully;
    return;
}
loop1:
    i = 0;
loop2:
    /*指示点1*/
    while (mutex->lock_word ! = 0 && i < SPIN_ROUNDS) {
             random spin using ut_delay, spin max time depend on SPIN_WAIT_DELAY;
             i++;
}
if (i == SPIN_ROUNDS) {
    yield_cpu;
}
/*指示点2*/
if (__sync_lock_test_and_set(mutex->lock_word, 1) == 0) {
    get mutex successfully;
    return;
}
if (i < SPIN_ROUNDS) {
     goto loop2
}
/*指示点4*/
get cell from sync array and call os_event_reset(mutex->event);
mutex->waiter =1;
/*指示点3*/
for (i = 0; i < 4; i++) {
    if (__sync_lock_test_and_set(mutex->lock_word, 1) == 0) {
        get mutex successfully;
        free cell;
        return;
    }
}
sync array wait and os_event_wait(mutex->event);
goto loop1;
```

代码还是有点小复杂的。这里分析几点如下：

1. SPIN_ROUNDS 控制了在放弃 cpu 时间片（yield_cpu）之前，一共进行多少次忙等，这个参数就是对外可配置的 innodb_sync_spin_loops，而 SPIN_WAIT_DELAY 控制了每次忙等的时间，这个参数也就是对外可配置的 innodb_spin_wait_delay。这两个参数一起决定了自旋的时间。Heikki Tuuri 建议在单处理器的机器上调小 spin 的时间，在对称多处理器的机器上，可以适当调大。比较有意思的是 innodb_spin_wait_delay 的单位，这个是 100MHZ 的奔腾处理器处理 1 毫秒的时间，默认 innodb_spin_wait_delay 配置成 6，表示最多在 100MHZ 的奔腾处理器上自旋 6 毫秒。由于现在 cpu 都是按照 GHZ 来计算的，所以按照默认配置自旋时间往往很短。此外，自旋不真是 cpu 傻傻的在那边 100%的跑，在现代的 cpu 上，给自旋专门提供了一条指令，在笔者的测试环境下，这条指令是 pause，查看 Intel 的文档，其对 pause 的解释是：不会发生用户态和内核态的切换，cpu 在用户态自旋，因此不会发生上下文切换，同时这条指令不会消耗太多的能耗。。。所以那些说 spin lock 太浪费电的不攻自破了。。。另外，编译器也不会把 ut_delay 给优化掉，因为其里面估计修改了一个全局变量。
2. yield_cpu 操作在笔者的环境中，就是调用了 pthread_yield 函数，这个函数把放弃当前 cpu 的时间片，然后把当前线程放到 cpu 可执行队列的末尾。
3. 在指示点 1 后面的循环，没有采用原子操作读取数据，是因为，Heikki Tuuri 认为由于原子操作在内存和 cpu cache 之间会产生过的数据交换，如果只是读本地的 cache，可以减少总线的争用。即使本地读到脏的数据，也没关系，因为在跳出循环的指示点 2，依然会再一次使用原子操作进行校验。
4. get cell 这个操作是从 sync array 执行的，sync array 详见辅助数据结构这一节，简单的说就是提供给监控线程使用的。
5. 注意一下，os_event_reset 和 os_event_wait 这两个函数的调用位置，另外，有一点必须清楚，就是 os_event_set（锁持有者释放所后会调用这个函数通知所有等待者）可能在这整段代码执行到任意位置出现，有可能出现在指示点 4 的位置，这样就构成了条件变量通知在条件变量等待之前，会造成无限等待。为了解决这个问题，才有了指示点 3 下面的代码，需要重新再次检测一下 lock_word，另外，即使 os_event_set 发生在 os_event_reset 之后，有了这些代码，也能让当前线程提前拿到锁，不用执行后续 os_event_wait 的代码，一定程度上提高了效率。

mutex_exit 的伪代码就简单多了，如下：

```shell
__sync_lock_test_and_set(mutex->lock_word, 0);
/* A problem: we assume that mutex_reset_lock word                                                                     
        is a memory barrier, that is when we read the waiters                                                                  
        field next, the read must be serialized in memory                                                                      
        after the reset. A speculative processor might                                                                         
        perform the read first, which could leave a waiting                                                                    
        thread hanging indefinitely.                                                                                                                                                                                                                        
Our current solution call every second                                                                                 
        sync_arr_wake_threads_if_sema_free()                                                                                   
        to wake up possible hanging threads if                                                                                 
        they are missed in mutex_signal_object. */ 
if (mutex->waiter != 0) {
     mutex->waiter = 0;
     os_event_set(mutex->event);
}
```

1. waiter 是 ib_mutex_t 中的一个变量，用来表示当前是否有线程在等待这个锁。整个代码逻辑很简单，就是先把 lock_word 设置为 0，然后如果发现有等待者，就把所有等待者给唤醒。facebook 的 mark callaghan 在 2014 年测试过，相比现在已经比较完善的 pthread 库，InnoDB 自旋互斥锁只在并发量相对较低（小于 256 线程）和锁等待时间比较短的情况下有优势，在高并发且较长的锁等待时间情况下，退化比较严重，其中一个很重要的原因就是 InnoDB 自旋互斥锁在锁释放的时候需要唤醒所有等待者。由于 os_event_ret 底层通过 pthread_cond_boardcast 来通知所有的等待者，一种改进是把 pthread_cond_boardcast 改成 pthread_cond_signal，即只唤醒一个线程，但 Inaam Rana Mark 测试后发现，如果只唤醒一个线程的话，在高并发的情况下，这个线程可能不会立刻被 cpu 调度到。。由此看来，似乎唤醒一个特定数量的等待者是一个比较好的选择。
2. 伪代码中的这段注释笔者估计加上去的，大意是由于编译器或者 cpu 的指令重排乱序执行，mutex->waiter 这个变量的读取可能在发生在原子操作之前，从而导致一些无线等待的问题。然后还专门开了一个叫做 sync_arr_wake_threads_if_sema_free 的函数来做清理。这个函数是在后台线程 srv_error_monitor_thread 中做的，每隔 1 秒钟执行一次。在现代的 cpu 和编译器上，完全可以用内存屏障的技术来防止指令重排和乱序执行，这个函数可以被去掉，官方的意见貌似是，不要这么激进，万一其他地方还需要这个函数呢。。详见 BUG #79477。

总体来说，InnoDB 自旋互斥锁的底层实现还是比较有意思的，非常适合学习研究。这套锁机制在现在完善的 Pthread 库和高达 4GMHZ 的 cpu 下，已经有点力不从心了，mark callaghan 研究发现，在高负载的压力下，使用这套锁机制的 InnoDB，大部分 cpu 时间都给了 sys 和 usr，基本没有空闲，而 pthread mutex 在相同情况下，却有平均 80%的空闲。同时，由于 ib_mutex_t 这个结构体体积比较庞大，当 buffer pool 比较大的时候，会发现锁占用了很多的内存。最后，从代码风格上来说，有不少代码没有解耦，如果需要把锁模块单独打成一个函数库，比较困难。 基于上述几个缺陷，MySQL 5.7 及后续的版本中，对互斥锁进行了大量的重新，包括以下几点(WL#6044)：

1. 使用了 C++中的类继承关系，系统互斥锁和 InnoDB 自己实现的自旋互斥锁都是一个父类的子类。
2. 由于 bool pool 的锁对性能要求比较高，因此使用静态继承（也就是模板）的方式来减少继承中虚指针造成的开销。
3. 保留旧的 InnoDB 自旋互斥锁，并实现了一种基于 futex 的锁。简单的说，futex 锁与上述的原子操作类似，能减少用户态和内核态切换的开销，但同时保留类似 mutex 的使用方法，大大降低了程序编写的难度。

## InnoDB 读写锁

与条件变量、互斥锁不同，InnoDB 里面没有 Pthread 库的读写锁的包装，其完全依赖依赖于原子操作和 InnoDB 的条件变量，甚至都不需要依赖 InnoDB 的自旋互斥锁。此外，读写锁还实现了写操作的递归锁，即同一个线程可以多次获得写锁，但是同一个线程依然不能同时获得读锁和写锁。InnoDB 读写锁的核心数据结构 rw_lock_t 中，并没有等待队列的信息，因此不能保证先到的请求一定会先进入临界区。这与系统互斥量用 PTHREAD_MUTEX_ADAPTIVE_NP 来初始化有异曲同工之妙。 InnoDB 读写锁的核心实现在源文件 sync0rw.cc 和 sync0rw.ic 中，核心数据结构 rw_lock_t 定义在 sync0rw.h 中。使用方法与 InnoDB 自旋互斥锁很类似，只不过读请求和写请求要调用不同的函数。加读锁调用`rw_lock_s_lock`, 加写锁调用`rw_lock_x_lock`，释放读锁调用`rw_lock_s_unlock`, 释放写锁调用`rw_lock_x_unlock`，创建读写锁调用`rw_lock_create`，释放读写锁调用`rw_lock_free`。函数`rw_lock_x_lock_nowait`和`rw_lock_s_lock_nowait`表示，当加读写锁失败的时候，直接返回，而不是自旋等待。

### 核心机制

rw_lock_t 中，核心的成员有以下几个：lock_word, event, waiters, wait_ex_event，writer_thread, recursive。 与 InnoDB 自旋互斥锁的 lock_word 不同，rw_lock_t 中的 lock_word 是 int 型，注意不是 unsigned 的，其取值范围是(-2X_LOCK_DECR, X_LOCK_DECR]，其中 X_LOCK_DECR 为 0x00100000，差不多 100 多 W 的一个数。在 InnoDB 自旋互斥锁互斥锁中，lock_word 的取值范围只有 0，1，因为这两个状态就能把互斥锁的所有状态都表示出来了，也就是说，只需要查看一下这个 lock_word 就能确定当前的线程是否能获得锁。rw_lock_t 中的 lock_word 也扮演了相同的角色，只需要查看一下当前的 lock_word 落在哪个取值范围中，就确定当前线程能否获得锁。至于 rw_lock_t 中的 lock_word 是如何做到这一点的，这其实是 InnoDB 读写锁乃至 InnoDB 同步机制中最神奇的地方，下文我们会详细分析。 event 是一个 InnoDB 条件变量，当当前的锁已经被一个线程以写锁方式独占时，后续的读锁和写锁都等待在这个 event 上，当这个线程释放写锁时，等待在这个 event 上的所有读锁和写锁同时竞争。waiters 这变量，与 event 一起用，当有等待者在等待时，这个变量被设置为 1，否则为 0，锁被释放的时候，需要通过这个变量来判断有没有等待者从而执行 os_event_set。 与 InnoDB 自旋互斥锁不同，InnoDB 读写锁还有 wait_ex_event 和 recursive 两个变量。wait_ex_event 也是一个 InnoDB 条件变量，但是它用来等待第一个写锁（因为写请求可能会被先前的读请求堵住），当先前到达的读请求都读完了，就会通过这个 event 来唤醒这个写锁的请求。 由于 InnoDB 读写锁实现了写锁的递归，因此需要保存当前写锁被哪个线程占用了，后续可以通过这个值来判断是否是这个线程的写锁请求，如果是则加锁成功，否则失败，需要等待。线程的 id 就保存在 writer_thread 这个变量中。 recursive 是个 bool 变量，用来表示当前的读写锁是否支持递归写模式，在某些情况下，例如需要另外一个线程来释放这个读写锁（insert buffer 需要这个功能）的时候，就不要开启递归模式了。

接下来，我们来详细介绍一下 lock_word 的变化规则：

1. 当有一个读请求加锁成功时，lock_word 原子递减 1。
2. 当有一个写请求加锁成功时，lock_word 原子递减 X_LOCK_DECR。
3. 如果读写锁支持递归写，那么第一个递归写锁加锁成功时，lock_word 依然原子递减 X_LOCK_DECR，而后续的递归写锁加锁成功是，lock_word 只是原子递减 1。 在上述的变化规则约束下，lock_word 会形成以下几个区间： lock_word == X_LOCK_DECR: 表示锁空闲，即当前没有线程获得了这个锁。 0 \< lock_word \< X_LOCK_DECR: 表示当前有 X_LOCK_DECR - lock_word 个读锁 lock_word == 0: 表示当前有一个写锁 -X_LOCK_DECR \< lock_word \< 0: 表示当前有-lock_word 个读锁，他们还没完成，同时后面还有一个写锁在等待 lock_word \<= -X_LOCK_DECR: 表示当前处于递归锁模式，同一个线程加了 2 - (lock_word + X_LOCK_DECR)次写锁。 另外，还可以得出以下结论
4. 由于 lock_word 的范围被限制（rw_lock_validate）在(-2X_LOCK_DECR, X_LOCK_DECR]中，结合上述规则，可以推断出，一个读写锁最多能加 X_LOCK_DECR 个读锁。在开启递归写锁的模式下，一个线程最多同时加 X_LOCK_DECR+1 个写锁。
5. 在读锁释放之前，lock_word 一定处于(-X_LOCK_DECR, 0)U(0, X_LOCK_DECR)这个范围内。
6. 在写锁释放之前，lock_word 一定处于(-2\*X_LOCK_DECR, -X_LOCK_DECR]或者等于 0 这个范围内。
7. 只有在 lock_word 大于 0 的情况下才可以对它递减。有一个例外，就是同一个线程需要加递归写锁的时候，lock_word 可以在小于 0 的情况下递减。

接下来，举个读写锁加锁的例子，方便读者理解读写锁底层加锁的原理。假设有读写加锁请求按照以下顺序依次到达：R1->R2->W1->R3->W2->W3->R4，其中 W2 和 W3 是属于同一个线程的写加锁请求，其他所有读写请求均来自不同线程。初始化后，lock_word 的值为 X_LOCK_DECR（十进制值为 1048576）。R1 读加锁请求首先到，其发现 lock_word 大于 0，表示可以加读锁，同时 lock_word 递减 1，结果为 1048575，R2 读加锁请求接着来到，发现 lock_word 依然大于 0，继续加读锁并递减 lock_word，最终结果为 1048574。注意，如果 R1 和 R2 几乎是同时到达，即使时序上是 R1 先请求，但是并不保证 R1 首先递减，有可能是 R2 首先拿到原子操作的执行权限。如果在 R1 或者 R2 释放锁之前，写加锁请求 W1 到来，他发现 lock_word 依旧大于 0，于是递减 X_LOCK_DECR，并把自己的线程 id 记录在 writer_thread 这个变量里，再检查 lock_word 的值（此时为-2），由于结果小于 0，表示前面有未完成的读加锁请求，于是其等待在 wait_ex_event 这个条件变量上。后续的 R3, W2, W3, R4 请求发现 lock_word 小于 0，则都等待在条件变量 event 上，并且设置 waiter 为 1，表示有等待者。假设 R1 先释放读锁(lock_word 递增 1)，R2 后释放(lock_word 再次递增 1)。R2 释放后，由于 lock_word 变为 0 了，其会在 wait_ex_event 上调用 os_event_set，这样 W3 就被唤醒了，他可以执行临界区内的代码了。W3 执行完后，lock_word 被恢复为 X_LOCK_DECR，然后其发现 waiter 为 1，表示在其后面有新的读写加锁请求在等待，然后在 event 上调用 os_event_set，这样 R3, W2, W3, R4 同时被唤醒，进行原子操作执行权限争抢(可以简单的理解为谁先得到 cpu 调度)。假设 W2 首先抢到了执行权限，其会把 lock_word 再次递减为 0 并自己的线程 id 记录在 writer_thread 这个变量里，当检查 lock_word 的时候，发现值为 0，表示前面没有读请求了，于是其就进入临界区执行代码了。假设此时，W3 得到了 cpu 的调度，由于 lock_word 只有在大于 0 的情况下才能递减，所以其递减 lock_word 失败，但是其通过对比 writer_thread 和自己的线程 id，发现前面的写锁是自己加的，如果这个时候开启了递归写锁，即 recursive 值为 true，他把 lock_word 再次递减 X_LOCK_DECR（现在 lock_word 变为-X_LOCK_DECR 了），然后进入临界区执行代码。这样就保证了同一个线程多次加写锁也不发生死锁，也就是递归锁的概念。后续的 R3 和 R4 发现 lock_word 小于等于 0，就直接等待在 event 条件变量上，并设置 waiter 为 1。直到 W2 和 W3 都释放写锁，lock_word 又变为 X_LOCK_DECR，最后一个释放的，检查 waiter 变量发现非 0，就会唤醒 event 上的所有等待者，于是 R3 和 R4 就可以执行了。 读写锁的核心函数函数结构跟 InnoDB 自旋互斥锁的基本相同，主要的区别就是用 rw_lock_x_lock_low 和 rw_lock_s_lock_low 替换了__sync_lock_test_and_set 原子操作。rw_lock_x_lock_low 和 rw_lock_s_lock_low 就按照上述的 lock_word 的变化规则来原子的改变（依然使用了__sync_lock_test_and_set）lock_word 这个变量。

在 MySQL 5.7 中，读写锁除了可以加读锁(Share lock)请求和加写锁(exclusive lock)请求外，还可以加 share exclusive 锁请求，锁兼容性如下：

```plaintext
 LOCK COMPATIBILITY MATRIX
    S SX  X
 S  +  +  -
 SX +  -  -
 X  -  -  -
```

按照 WL#6363 的说法，是为了修复 index->lock 这个锁的冲突。

## 辅助结构

InnoDB 同步机制中，还有很多使用的辅助结构，他们的作用主要是为了监控方便和死锁的预防和检测。这里主要介绍 sync array, sync thread level array 和 srv_error_monitor_thread。 sync array 主要的数据结构是 sync_array_t，可以把他理解为一个数据，数组中的元素为 sync_cell_t。当一个锁（InnoDB 自旋互斥锁或者 InnoDB 读写锁，下同）需要发生`os_event_wait`等待时，就需要在 sync array 中申请一个 sync_cell_t 来保存当前的信息，这些信息包括等待锁的指针（便于死锁检测），在哪一个文件以及哪一行发生了等待（也就是 mutex_enter, rw_lock_s_lock 或者 rw_lock_x_lock 被调用的地方，只在 debug 模式下有效），发生等待的线程（便于死锁检测）以及等待开始的时间（便于统计等待的时间）。当锁释放的时候，就把相关联的 sync_cell_t 重置为空，方便复用。sync_cell_t 在 sync_array_t 中的个数，是在初始化同步模块时候就指定的，其个数一般为 OS_THREAD_MAX_N，而 OS_THREAD_MAX_N 是在 InnoDB 初始化的时候被计算，其包括了系统后台开启的所有线程，以及 max_connection 指定的个数，还预留了一些。由于一个线程在某一个时刻最多只能发生一个锁等待，所以不用担心 sync_cell_t 不够用。从上面也可以看出，在每个锁进行等待和释放的时候，都需要对 sync array 操作，因此在高并发的情况下，单一的 sync array 可能成为瓶颈，在 MySQL 5.6 中，引入了多 sync array, 个数可以通过 innodb_sync_array_size 进行控制，这个值默认为 1，在高并发的情况下，建议调高。 InnoDB 作为一个成熟的存储引擎，包含了完善的死锁预防机制和死锁检测机制。在每次需要锁等待时，即调用`os_event_wait`之前，需要启动死锁检测机制来保证不会出现死锁，从而造成无限等待。在每次加锁成功（lock_word 递减后，函数返回之前）时，都会启动死锁预防机制，降低死锁出现的概率。当然，由于死锁预防机制和死锁检测机制需要扫描比较多的数据，算法上也有递归操作，所以只在 debug 模式下开启。 死锁检测机制主要依赖 sync array 中保存的信息以及死锁检测算法来实现。死锁检测机制通过 sync_cell_t 保存的等待锁指针和发生等待的线程以及教科书上的有向图环路检测算法来实现，具体实现在`sync_array_deadlock_step`和`sync_array_detect_deadlock`中实现，仔细研究后发现个小问题，由于`sync_array_find_thread`函数仅仅在当前的 sync array 中遍历，当有多个 sync array 时（innodb_sync_array_size > 1）,如果死锁发生在不同的 sync array 上，现有的死锁检测算法将无法发现这个死锁。 死锁预防机制是由 sync thread level array 和全局锁优先级共同保证的。InnoDB 为了降低死锁发生的概率，上层的每种类型的锁都有一个优先级。例如回滚段锁的优先级就比文件系统 page 页的优先级高，虽然两者底层都是 InnoDB 互斥锁或者 InnoDB 读写锁。有了这个优先级，InnoDB 规定，每个锁创建是必须制定一个优先级，同一个线程的加锁顺序必须从优先级高到低，即如果一个线程目前已经加了一个低优先级的锁 A，在释放锁 A 之前，不能再请求优先级比锁 A 高(或者相同)的锁。形成死锁需要四个必要条件，其中一个就是不同的加锁顺序，InnoDB 通过锁优先级来降低死锁发生的概率，但是不能完全消除。原因是可以把锁设置为 SYNC_NO_ORDER_CHECK 这个优先级，这是最高的优先级，表示不进行死锁预防检查，如果上层的程序员把自己创建的锁都设置为这个优先级，那么 InnoDB 提供的这套机制将完全失效，所以要养成给锁设定优先级的好习惯。sync thread level array 是一个数组，每个线程单独一个，在同步模块初始化时分配了 OS_THREAD_MAX_N 个，所以不用担心不够用。这个数组中记录了某个线程当前锁拥有的所有锁，当新加了一个锁 B 时，需要扫描一遍这个数组，从而确定目前线程所持有的锁的优先级都比锁 B 高。 最后，我们来讲讲 srv_error_monitor_thread 这个线程。这是一个后台线程，在 InnoDB 启动的时候启动，每隔 1 秒钟执行一下指定的操作。跟同步模块相关的操作有两点，去除无限等待的锁和报告长时间等待的异常锁。 去除无线等待的锁，如上文所属，就是 sync_arr_wake_threads_if_sema_free 这个函数。这个函数通过遍历 sync array，如果发现锁已经可用(`sync_arr_cell_can_wake_up`)，但是依然有等待者，则直接调用`os_event_set`把他们唤醒。这个函数是为了解决由于 cpu 乱序执行或者编译器指令重排导致锁无限等待的问题，但是可以通过内存屏障技术来避免，所以可以去掉。 报告长时间等待的异常锁，通过 sync_cell_t 里面记录的锁开始等待时间，我们可以很方便的统计锁等待发生的时间。在目前的实现中，当锁等待超过 240 秒的时候，就会在错误日志中看到信息。如果同一个锁被检测到等到超过 600 秒且连续 10 次被检测到，则 InnoDB 会通过 assert 来自杀。。。相信当做运维 DBA 的同学一定看到过如下的报错：

```shell
InnoDB: Warning: a long semaphore wait:
--Thread 139774244570880 has waited at log0read.h line 765 for 241.00 seconds the semaphore:
Mutex at 0x30c75ca0 created file log0read.h line 522, lock var 1 
Last time reserved in file /home/yuhui.wyh/mysql/storage/innobase/include/log0read.h line 765, waiters flag 1
InnoDB: ###### Starts InnoDB Monitor for 30 secs to print diagnostic info:
InnoDB: Pending preads 0, pwrites 0
```

一般出现这种错误都是 pread 或者 pwrite 长时间不返回，导致锁超时。至于 pread 或者 pwrite 长时间不返回的 root cause 常常是有很多的读写请求在极短的时间内到达导致磁盘扛不住或者磁盘已经坏了。。。

## 总结

本文详细介绍了原子操作，条件变量，互斥锁以及读写锁在 InnoDB 引擎中的实现。原子操作由于其能减少不必要的用户态和内核态的切换以及更精简的 cpu 指令被广泛的应用到 InnoDB 自旋互斥锁和 InnoDB 读写锁中。InnoDB 条件变量使用更加方便，但是一定要注意条件通知必须在条件等待之后，否则会有无限等待发生。InnoDB 自旋互斥锁加锁和解锁过程虽然复杂但是都是必须的操作。InnoDB 读写锁神奇的 lock_word 控制方法给我们留下了深刻影响。正因为 InnoDB 底层同步机制的稳定、高效，MySQL 在我们的服务器上才能运行的如此稳定。
