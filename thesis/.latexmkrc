# pdfLaTeX + BibTeX. Products stay next to main.tex (see thesis/.gitignore).
$pdf_mode = 1;
$bibtex_use = 2;
$do_cd = 1;
$pdflatex = 'pdflatex -interaction=nonstopmode -file-line-error -synctex=1 %O %S';
