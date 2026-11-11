# 扩展故障目录（F06–F20，M2 实现）

5 类核心故障（F01–F05）之外的 15 个扩展用例，按证据可得性与注入难度排序，M2 周补齐实现与金标签：

| id | 名称 | 类别 | 注入方式（草案） |
|---|---|---|---|
| F06 | zombie_process_pileup | resource/process | 大量子进程 exit 后父进程不 wait |
| F07 | fd_exhaustion | resource/fd | ulimit -n 内打开文件直至 EMFILE |
| F08 | inode_exhaustion | resource/disk | 在 tmpfs 创建海量小文件直至 inode 耗尽 |
| F09 | bad_config | config/error | 备份后写入损坏的配置文件，重启服务 |
| F10 | log_flood | log/storm | 高频写 /var/log/medic 形成日志风暴 |
| F11 | oom_kill_event | resource/memory | F01 变体：低内存上限下记录 OOM kill 事件链 |
| F12 | dns_failure | network/dns | 改写 /etc/resolv.conf 指向不可达地址 |
| F13 | permission_error | security/permission | chmod 关键文件权限导致服务启动失败 |
| F14 | io_latency | resource/io | dm-delay/FUSE 玩具 FS 制造 IO 高延迟 |
| F15 | swap_exhaustion | resource/memory | 填充内存 + swap 直至耗尽 |
| F16 | process_deadlock | process/deadlock | 两进程互锁 fcntl 锁 |
| F17 | service_dependency_cycle | service/dependency | 玩具服务依赖环（A 等 B，B 等 A） |
| F18 | port_conflict | network/port | 占用 8080 端口导致服务无法绑定 |
| F19 | clock_jump | env/time | 修改容器时间基线（libfaketime 或应用层） |
| F20 | high_latency_variant | network/loss | tc netem 纯高延迟变体（loss 0%, delay 800ms） |
