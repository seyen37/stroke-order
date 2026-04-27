---
layout: default
---

# ?典 GitHub 摰甇仿?

?敺?堆?2026-04-26 繚 撠? v0.13.0 擐活?祇??券?
---

## ?蔭蝣箄?

1. 雿? GitHub repo 撌脣遣憟賭???*蝛箇?**嚗???README????LICENSE???遙雿?獢?嚗?   - URL嚗https://github.com/seyen37/stroke-order`
   - ??repo 銝蝛箇?嚗???GitHub Settings ???芷?遣嚗? clone 銝?????
2. 雿??祆? Git 撌脰身憟?SSH key ??HTTPS 隤?嚗 push ?啗撌梁? GitHub
   ```bash
   ssh -T git@github.com
   # ?＊蝷?"Hi seyen37! You've successfully authenticated, ??
   ```
   ?仿?瘝身憟質?霅????? [`GIT_AUTH_SETUP.md`](GIT_AUTH_SETUP.md)嚗 SSH / HTTPS / GitHub CLI 銝車?孵? + 銝?璆剔頂蝯望?撘?

3. 蝣箄??祆? Git ?典?閮剖?嚗ommit author ?典?銝?嚗?   ```bash
   git config --global user.name        # ?＊蝷箝迂憯怠膝?? seyen37
   git config --global user.email       # ?＊蝷?seyen37@gmail.com
   ```
   ?交?閮剝?嚗嚗?   ```bash
   git config --global user.name "閮勗ㄚ敶?
   git config --global user.email "seyen37@gmail.com"
   ```

---

## Step 1嚗????祆???蝡舀?

cd ??stroke-order 撠???函?鞈?憭整?嚗?
```bash
cd ~/path/to/stroke-order
```

蝣箄?雿撠?鞈?憭橘?
```bash
ls
# ?府? README.md, pyproject.toml, src/, tests/, docs/, ... 蝑?```

---

## Step 2嚗???Cowork sandbox ????摰 .git

Cowork ?岫???? mount filesystem 銝?閮勗神??lock 瑼???銝??*蝛箸挺 .git/**??皜?嚗?
```bash
rm -rf .git
ls -a | grep '^.git'    # 蝣箄???皜征嚗閰脩???.gitignore .github嚗???.git嚗?```

---

## Step 3嚗?憪? git + 閮剖???repo ??author

```bash
git init -b main

# 蝣箄? author ?舐?擃葉?????????嚗?git config user.name  "閮勗ㄚ敶?
git config user.email "seyen37@gmail.com"
```

> ?乩??唾?**??repo ?身摰?*頝??git config 銝?嚗閂憒??望???嚗?銝 local config ??override ?典????典??喳??
---

## Step 4嚗???commit嚗?撖衣? ??4 ??commits嚗?其?憭?timestamp嚗?
> **?**嚗? `docs/decisions/`?????撖衣????賡???瘜滬 / 閮渲??虜????靽∪漲????commit ?賣隞予??撖行????? GitHub server-side push timestamp 撠望撘瑁???
### Commit 1嚗??潸?蝯∟???銵?霈?reviewer 銝??撠梁???narrative嚗?
```bash
git add docs/
git status                       # 蝣箄???add 鈭?docs/
git commit -m "docs: import development records (decisions/, WORK_LOG, GALLERY_DEPLOYMENT, QUICK_START)

This repository's git history begins on 2026-04-26 with v0.13.0
first-time publication, but the codebase itself was developed locally
across 67 internal phases (Phase 1 ??Phase 5g) prior to this commit.

The decision logs in docs/decisions/ retroactively reconstruct the
key design choices, alternatives considered, difficulties encountered,
and final solutions, based on phase tags + design comments + test
docstrings embedded in the source code.

See README.md '?甇瑞?' section + docs/HISTORY.md (when produced)
for the full timeline."
```

### Commit 2嚗?蝣?
```bash
git add src/
git status
git commit -m "feat: import source code at v0.13.0

- 9 web UI modes: ?桀? / 摮? / 蝑? / 靽∠? / 蝔輻? / 憛? / ????/
  蝑?蝺渡? (5d) / ?祉?澈摨?(5g)
- 13 character data sources: g0v / mmh / kanjivg / cns_font /
  punctuation / user_dict / chongxi_seal / moe_lishu / moe_song /
  moe_kaishu / cns_components / cns_strokes
- Independent gallery package with email magic-link auth + SQLite
- ~5000 lines of Python + 6 ES module frontend"
```

### Commit 3嚗葫閰血?隞?
```bash
git add tests/
git status
git commit -m "test: import test suite (1057 tests, 41 skipped)

Phase 1 ??5g coverage:
- Character IR + classifier + smoothing + validation
- 13 source adapters
- All 9 web UI modes incl. routing + rendering
- Gallery 19 core + 24 API tests (5g)
- Handwriting page 26 tests (5d)
- Sutra mode evolution 5bv ??5cc"
```

### Commit 4嚗?獢葉蝜潸???+ CI

```bash
git add pyproject.toml LICENSE README.md REF_ANALYSIS_*.md \
        .gitignore .github/
git status
git commit -m "chore: project metadata, MIT LICENSE, GitHub Actions CI

- pyproject.toml: package + 4 optional extras (web/gif/all/dev)
- LICENSE: MIT for code; third-party data sources retain own licenses
- README.md: badges, dev history note, install + run instructions
- .github/workflows/ci.yml: pytest matrix on Python 3.10/3.11/3.12
  for both push and PR. Each CI run leaves a public timestamp."
```

### 蝣箄? 4 ??commits ?賢末鈭?
```bash
git log --oneline
# ?府憿舐內 4 銵???啣銝?嚗?#   <hash>  chore: project metadata, MIT LICENSE, ...
#   <hash>  test: import test suite (1057 tests, 41 skipped)
#   <hash>  feat: import source code at v0.13.0
#   <hash>  docs: import development records (...)
```

---

## Step 5嚗? remote 銝?push

```bash
git remote add origin git@github.com:seyen37/stroke-order.git

# 銋?寧 HTTPS嚗瘝身 SSH key嚗?
# git remote add origin https://github.com/seyen37/stroke-order.git

# 蝣箄? remote 閮剖末
git remote -v

# Push
git push -u origin main
```

push 摰?敺 https://github.com/seyen37/stroke-order ??
- 4 ??commits ?賢
- README 憿舐內 5 ??badges嚗I ???????ending???nknown??蝑?CI 頝???嚗?- LICENSE ?????IT??蝷?
---

## Step 6嚗? GitHub Actions CI 頝?

Push 敺?GitHub ?芸?閫貊 CI嚗.github/workflows/ci.yml`嚗?

1. ??`https://github.com/seyen37/stroke-order/actions`
2. ???唬?蝑I?un ?刻?嚗??脣???
3. 蝝?3?? ??敺?蝬?pytest 1057 璇蝬?閰梧?
4. 霈?敺?README 銝? CI badge 銋??芸?霈assing??
**???靽風銝??甇仿?**嚗?甈?CI run ?賣? GitHub server-side timestamp + 摰 log嚗銝?賡?蝚砌??寡???霅?雿? code ??N ??N ?仿????? 1057 ?葫閰艾?
> ??CI 憭望?嚗虜??cairo 蝟餌絞靘陷??Python ??賊??????仃??log嚗?隤方??航矽??`.github/workflows/ci.yml`?虜閬???
>
> - **`No module named 'fastapi'`** ??`pip install -e ".[dev]"` 瘝?憟踝?瑼Ｘ pyproject ??dev extras
> - **`cairosvg.surface.UnsupportedSVG...`** ??蝟餌絞 cairo 摨怎撩嚗I yaml ??`apt-get install libcairo2-dev`
> - **CJK font 蝻?*嚗fonts-noto-cjk` ?身瘝?嚗I runs ?航頝喲??典??閬?CJK ??raster 皜祈岫

---

## Step 7嚗?訾??刻嚗?鋆? v0.13.0 git tag

```bash
git tag -a v0.13.0 -m "First public release: 9 web UI modes, 1057 tests passing

This is the first public commit of stroke-order, after extensive local
development across 67 internal phases. See docs/decisions/ for the
full design history."

git push origin v0.13.0
```

銋? https://github.com/seyen37/stroke-order/releases ?臭誑?箸??tag 撱箇?甇????GitHub Release嚗 release notes???頛?zip嚗?
---

## Step 8嚗撥??甈????舫嚗?
### 8a. ?? branch protection
- GitHub ??Settings ??Branches ??Add rule for `main`
- ?暸?equire pull request before merging???equire status checks (CI)??- ?脫迫?芯??芸楛隤斤??push ?游? history

### 8b. GPG sign commits嚗??GPG key嚗?```bash
git config --global user.signingkey YOUR_GPG_KEY_ID
git config --global commit.gpgsign true
```
銋?瘥?commit ?賣?撣嗥偷蝡?GitHub 憿舐內?erified?噬蝡?
### 8c. OpenTimestamps嚗?鞎?blockchain ?嚗?```bash
# ???commit hash 銝?
ots stamp .git/refs/heads/main
```
?Ｙ???`.ots` 瑼雿????X ??????git ???撖Ⅳ摮貉????⊥?鈭??賡?
### 8d. ?箸撅??甈閮??祉內??嚗??啁雿??瞈?箸撅?唾???甈閮??撥?塚?雿迄閮????祉內霅???- 銵冽嚗蝬??冽?扯瓷?Ｗ???甈閮(https://www.tipo.gov.tw/)

---

## Step 9嚗?敺?蝬剛風敺芰

瘥活?祆??孵?銝畾萄??踝?

```bash
# 蝺刻摩蝔?蝣?/ ?辣
git status                 # ?鈭?暻?git add <files>
git commit -m "feat(...): ..."
git push
```

> ??嚗ommit message 撖怨底蝝圈?撠靘撌望?撟怠嚗onventional Commits ?澆?嚗feat:`/`fix:`/`docs:`/`test:`/`chore:`/`refactor:`/`perf:`嚗靘輻 `git log --oneline` 銝?潭???
---

## 撣貉???

### Q: push ??GitHub ???ain 頝?master 銵???GitHub ?身??repo ??`main` branch嚗?憒??? git ?身 `master`嚗??對?
```bash
git branch -M main
git push -u origin main
```

### Q: SSH key 瘝身憟踝??賜 HTTPS push ??
?臭誑嚗?```bash
git remote set-url origin https://github.com/seyen37/stroke-order.git
git push
# ?歲?箏董??蝣潭?蝷箝TTPS ?閬?Personal Access Token嚗??舐?亙?蝣潘?嚗?# ??GitHub Settings ??Developer settings ??Personal access tokens ?唾?
```

### Q: CI 頝??Ｕ??
- ??Actions ?暺府 run ???ancel workflow??- ? commit message ??`[skip ci]` 頝喲? CI嚗??活銝遣霅啗歲嚗?
### Q: ???commit author 憿舐內?箄?llen Hsu??
local config ??user.name ?喳嚗?```bash
git config user.name "Allen Hsu"
# 瘜冽?嚗敶梢??敺? commit嚗風??commit 閬?amend / rebase ???```

撠?甈蔣?選??望???vs 銝剜???荔?????*頝? pyproject.toml 頝?LICENSE 銝??*???遣霅唳蝯曹??具迂憯怠膝?葉??雿?pyproject 撌脩??舫?
### Q: ?神??撘Ⅳ鋆⊥??乩犖??撘Ⅳ?獐颲佗?
- ?典 g0v / MMH / KanjiVG 蝑??? = OK嚗鈭??????鞈???LICENSE 頝?sources/ docstring
- ?典?乩犖??撘Ⅳ?挾 = 敹??冽?蝣潸酉???+ 閰脫挾蝔?蝣潛???
- ?典 stack overflow / blog ??靘?= 銝?砍?神嚗撖西釭?扳 > 10 銵?撱箄降閮餅?

---

## ?券???瑼Ｘ皜

- [ ] `https://github.com/seyen37/stroke-order` 憿舐內 4 ??commits + 雿?蝜葉憪?
- [ ] README 銝 5 ??badges ?賡＊蝷?- [ ] LICENSE 憿舐內 MIT
- [ ] `.github/workflows/ci.yml` ??Actions tab 頝?
- [ ] CI 霈?嚗adges ?芸??湔??passing嚗?- [ ] v0.13.0 tag ??Releases ??
- [ ] 嚗?賂?GPG signed commits 憿舐內 Verified 敺賜?
- [ ] ?芸楛 clone 銝隞賢?亦?鞈?憭暸?霅?push 摰嚗?      ```bash
      cd /tmp
      git clone git@github.com:seyen37/stroke-order.git
      cd stroke-order
      pip install -e ".[dev]"
      pytest tests/             # ?府 1057 passed
      ```

---

## 銋??啣?瘙箇??亥??極雿?

??憟賬?甈∪極雿???神瘙箇??亥???閬?閮 `.auto-memory/`嚗靘?閰望??芸?憟嚗?甈∪極雿????Ｗ `docs/decisions/<?唳?>.md` 敺?

```bash
git add docs/decisions/<?唳?>.md
git commit -m "docs: add decision log for <銝駁?>"
git push
```

瘥活 push ?賣?虫??洵銝? ??瞍賊脩敞蝛?????
---

摰? push 敺?閮湔?嚗??匱蝥? Batch 2 ?瘙箇??亥?嚗ode_02 / mode_03 / infra_02嚗?
