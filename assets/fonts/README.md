# Shiye Name Kai

`shiye-name-kai.woff2` is a 1,696-byte web font subset containing only
`雷诗叶` (U+96F7, U+8BD7, U+53F6). It is used for the Chinese name in the homepage header.

- CSS family: `Shiye Name Kai`
- Weight/style: `400` / `normal`
- Source: [LXGW WenKai official repository](https://github.com/lxgw/LxgwWenKai)
- Original font: `LXGWWenKai-Regular.ttf`, version 1.522 (March 17, 2026)
- Source revision: [`29acb395f27f55110c2427e3ac2de1c12553cf6e`](https://github.com/lxgw/LxgwWenKai/tree/29acb395f27f55110c2427e3ac2de1c12553cf6e)
- [Original font at that revision](https://raw.githubusercontent.com/lxgw/LxgwWenKai/29acb395f27f55110c2427e3ac2de1c12553cf6e/fonts/TTF/LXGWWenKai-Regular.ttf)
- Original SHA-256: `39ad71264b588165b469e35e6afb162a378dacd1f95348160240ba9038ac3009`
- Subset SHA-256: `270b46f0921b3ee32f2c3f0c41aaed64faf2803e6f660e2026a7ce5a52fa9ce2`

The original and subset are licensed under SIL Open Font License 1.1.
The full upstream copyright notices and license are included in
[`shiye-name-kai-OFL.txt`](shiye-name-kai-OFL.txt). The modified font's internal
family and PostScript names were changed to `Shiye Name Kai` and
`ShiyeNameKai-Regular` to avoid the upstream reserved font names.
Original copyright and license metadata remain in the subset.

## Reproduce the subset

Requires Python, fontTools, and Brotli. Download the original font from the pinned
official source above. The subset was created with fontTools 4.58.5 and Brotli 1.2.0:

```python
from fontTools import subset
from fontTools.ttLib import TTFont

font = TTFont("LXGWWenKai-Regular.ttf")
options = subset.Options()
options.flavor = "woff2"
options.hinting = False
options.notdef_outline = False
options.name_IDs = ["*"]
options.name_languages = ["*"]
subsetter = subset.Subsetter(options=options)
subsetter.populate(text="雷诗叶")
subsetter.subset(font)
family = "Shiye Name Kai"
names = {
    1: family, 2: "Regular", 3: "Shiye Name Kai Regular 1.522 subset",
    4: family + " Regular", 6: "ShiyeNameKai-Regular",
    16: family, 17: "Regular", 18: family + " Regular",
    21: family, 22: "Regular",
}
for record in font["name"].names:
    if record.nameID in names:
        record.string = names[record.nameID].encode(record.getEncoding())
for name_id, value in names.items():
    font["name"].setName(value, name_id, 3, 1, 0x409)
font.flavor = "woff2"
font.save("shiye-name-kai.woff2")
```
