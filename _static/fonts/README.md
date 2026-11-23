# Fonts

Both under the SIL Open Font License 1.1, see the `-OFL.txt` next to each.

- `google-sans-flex.woff2`: from `GoogleSansFlex[ROND,opsz,slnt,wdth,wght].ttf` in [google/fonts](https://github.com/google/fonts/tree/main/ofl/googlesansflex), weights 400-700 with the slant for italics, subset to Latin:

  ```sh
  fonttools varLib.instancer GoogleSansFlex*.ttf ROND=0 opsz=drop wdth=100 wght=400:700 slnt=-10:0 -o instance.ttf
  pyftsubset instance.ttf --unicodes="U+0020-007E,U+00A0-00FF,U+2010-2027,U+2030-203A,U+2190-2199,U+279C" \
    --layout-features="kern,liga,calt,tnum" --flavor=woff2 --output-file=google-sans-flex.woff2
  ```

- `source-code-pro.woff2`: Source Code Pro Regular.
