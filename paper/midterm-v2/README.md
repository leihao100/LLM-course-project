# 中期报告 version 2

这是 Jingjie 合并后的中期报告，放在单独的分支 `midterm-v2` 和单独的文件夹里。原有的 `paper/midterm/`、`release/` 以及其他所有文件都没有改动。

| 文件 | 内容 |
|---|---|
| `main.tex` | 报告源码。以 Jingjie 的版本为主体，并入了 Yuhao 的 Codex 先导实验（表 3）、57/60 空动作对照、route 格式问题和 Mantravadi 2026 的引用 |
| `main.pdf` | 编译结果，正好 4 页（含参考文献） |
| `neurips_2026.sty` | 课程 Overleaf 模板目前使用的官方样式，未修改，来自 NeurIPS 官网的 Formatting_Instructions_For_NeurIPS_2026.zip |
| `中期任务-给Yuhao.md` | 中期前要对齐和完成的事 |

这一份去掉了作者邮箱，因为本仓库是公开的。正式提交的版本按需要再加回来。

格式：`preprint` 模式（页脚显示 “Preprint.”，`final` 只给已被 NeurIPS 接收的论文用），参考文献字号为 `small`，这是官方说明允许的最小字号。

编译：把 `main.tex` 和 `neurips_2026.sty` 上传到 Overleaf，或在本目录运行 `tectonic main.tex`。

提交前还需要 Yuhao 确认：Contributions 段里他那一行，以及表 3 和 57/60 的数字。
