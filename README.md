# Clinical Chart Safety

LLM course project by Jingjie Qian and Yuhao Lei, Northeastern University.

本项目研究：当临床智能体与评分器共同读取损坏病历时，原评分器是否会接受偏离干净参考的医嘱，以及写入前的证据核验提示有什么局限。评价依据是明确声明的研究策略，不是实际患者伤害。

## 中期报告

- [四页英文报告，NeurIPS 2024 格式，含参考文献](release/midterm-report-neurips.pdf)
- [可直接上传 Overleaf 的源码包](release/midterm-report-overleaf.zip)
- [LaTeX 主文件](paper/midterm/midterm_report.tex)
- [课程评分要求、结果说明与复现说明](docs/中期报告说明.md)
- [完整双路径实测报告](docs/双路径实测报告.pdf)
- [实验协议](docs/实验协议.md)与[运行指南](docs/运行指南.md)
- [英文论文长稿](paper/manuscript.md)与[参考文献核验](docs/来源核验.md)

报告截至 2026-11-05。成员贡献段落依作者要求暂未填写，属于提交前仍需补齐的课程评分项。

## 当前结果

已完成原评分器的 8 项可复现审计与实际模型先导。最近一轮使用一致的输出格式，在已授权的同一份最小化两例输入上完成 6 次模型运行：6 次均通过原评分器，其中 2 次镁单位故障医嘱偏离干净参考。该结果仅证明选定病例中的机制，不代表总体风险率或干预有效性。

对 30 条既有 Codex 轨迹移除数值边界进行重评分，4 条暂缓标签发生变化，不安全动作布尔判定不变。此项是固定轨迹的策略敏感性分析。聚合结果见 [midterm-summary.json](results/midterm-summary.json)。三模型规模比较和人工解释盲审尚未完成。

## 本地运行

Python 3.10 以上，研究核心只使用标准库。在仓库根目录执行：

```bash
python -m unittest discover -s tests -v
python -m chartguard audit
python -m chartguard demo
```

测试共有 54 项。`audit` 使用保留的原始评分函数复现确定性反例；`demo` 执行 396 个适用的合成编程控制，另保留 54 个不适用条目。编程控制不是 LLM 实验，不可当作模型成绩。

公开仓库包含全部研究代码、配置、测试、文档、PDF/Word/LaTeX、合成样例和聚合结果。病历快照、患者级结果、原始推理日志、数据传输授权记录及模型权重保留在本地；完整本地包文档提及的这些路径在本仓库中可能不存在。`analyze_midterm.py` 等逐轨迹分析需要相应本地输入，聚合结果不能代替它们。

## 原基准与推理配置

任务文件可从固定版本的上游仓库单独获取，并校验其摘要：

```bash
python scripts/fetch_benchmark_tasks.py
python -m chartguard plan
```

真实病历按运行指南从本地 FHIR 服务只读导出。`vendor/` 保留上游源码、许可证与来源摘要，下载得到的任务文件默认不纳入 Git。

模型配置使用相对工作目录。CPU 模型脚本将运行时和权重放在本仓库的 `work/` 下，也可通过 `CHART_WORKSPACE_ROOT` 指定位置。Codex 配置使用现有 ChatGPT 登录；对原基准数据的云端调用仍要求匹配输入摘要的本地明确授权文件。公开仓库不包含或预先授予这项授权。

在 `paper/midterm/` 中运行 `tectonic midterm_report.tex` 或 `latexmk -pdf midterm_report.tex` 可编译中期报告。其官方样式文件未改动；来源见 [template-provenance.json](paper/midterm/template-provenance.json)。

## 项目结构

```text
chartguard/  故障注入、独立评分、SQLite 沙盒、模型客户端和统计
configs/     策略、模型与先导配置
tests/       研究行为和协议回归测试
scripts/     部署、分析、来源获取和文档构建脚本
data/        合成样例和人工审阅模板
results/     可公开的聚合结果及源码审计
docs/        中文研究文档及 PDF/Word
paper/       英文长稿、中期 LaTeX 与图表
release/     中期报告 PDF 与 Overleaf 源码包
vendor/      上游评分器、工具定义、执行器及许可证
```

扩展代码见 [LICENSE](LICENSE)；上游代码保留 [MedAgentBench MIT 声明](vendor/LICENSE.MedAgentBench)。
