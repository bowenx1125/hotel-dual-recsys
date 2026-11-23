# FYP-1 论文 LaTeX 骨架

这是学校 Word 模板的 LaTeX 移植，只保留版式和章节标题。正文留空或只有一行 `[TODO: ...]`。课程有 AI 检测限制，**正文必须由组员自己写**，不要把生成的段落提交进章节文件。

版式与模板一致：pdfLaTeX、`newtx`（Times）、正文 12pt、章标题 16pt、节标题 14pt、左右页边距 2cm、上下 2.5cm。

## 谁改哪个文件

同一时间一个文件只由一个人改。`main.tex` 只放导言区和 `\input`，平时不要改。

| 文件 | 建议负责人 | 内容 |
|---|---|---|
| `chapters/01-introduction.tex` | 成员 A | 第 1 章 Introduction |
| `chapters/02-literature-review.tex` | 成员 A | 第 2 章 Literature Review |
| `chapters/03-data.tex` | 成员 B | 第 3 章 Data |
| `chapters/04-methodology.tex` | 成员 B | 第 4 章 Methodology |
| `chapters/05-experiments.tex` | 成员 C | 第 5 章 Experiments and Discussion |
| `chapters/06-limitations.tex` | 成员 C | 第 6 章 Limitations and Future Work |
| `chapters/07-conclusion.tex` | 成员 C | 第 7 章 Conclusion |
| `chapters/appendix.tex` | 三人协商后一人改 | 附录 |
| `frontmatter/titlepage.tex` | 三人协商后一人改 | 封面 |
| `frontmatter/declaration.tex` | 三人协商后一人改 | 声明与各人章节职责 |
| `frontmatter/acceptance.tex` | 三人协商后一人改 | 接收页 |
| `frontmatter/acknowledgement.tex` | 三人协商后一人改 | 致谢 |
| `frontmatter/abstract.tex` | 三人协商后一人改 | 摘要（不超过 250 词） |
| `references.bib` | 谁引用谁添加条目 | 参考文献。每条都必须在正文里引用 |
| `figures/` | 谁用图谁放入 | 图片。在章节里用 `\includegraphics` |

姓名、学号、题目、导师填在 `main.tex` 顶部的 `\thesistitle`、`\memberA` 等命令里，改完告诉另外两人，避免两个人同时改这个文件。声明页里的 “In charge of / Responsible for Chapter” 要和上表一致。

## 本地编译

需要 TeX Live（pdfLaTeX，不要用 XeLaTeX 或 LuaLaTeX）：

```bash
cd thesis
latexmk -pdf main.tex
```

PDF 在 `thesis/main.pdf`。清理中间文件：

```bash
latexmk -c
```

`references.bib` 里未引用的占位条目会让 BibTeX 给出 warning，这不影响编译。有 LaTeX error 才算失败。

## 下载 CI 上的 PDF

推送到改动了 `thesis/**` 的分支，或打开这样的 Pull Request 时，GitHub Actions 工作流 **thesis-pdf**（`.github/workflows/thesis-pdf.yml`）会用 `xu-cheng/latex-action`、`latexmk` 和 pdfLaTeX 在 `thesis/` 下编译，并把 PDF 上传为名为 `thesis.pdf` 的 artifact。

下载步骤：

1. 打开仓库的 Actions 页，选中工作流 **thesis-pdf**。
2. 打开对应这次推送或 Pull Request 的成功运行。
3. 在页面底部的 Artifacts 里下载 `thesis.pdf`。

直接链接：<https://github.com/bowenx1125/hotel-dual-recsys/actions/workflows/thesis-pdf.yml>

不要把 `main.pdf` 或 LaTeX 中间文件提交进仓库。
