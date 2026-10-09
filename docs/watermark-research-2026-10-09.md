# Research: how might Kling embed an invisible image watermark?

2026-10-09. Detection only. This note collects what public sources say about Kling's (Kuaishou's) invisible watermark, and what that means for our tests. It is the basis for the new tests in `forensics/wmhunt.py` and for [watermark-hunt-plan.md](watermark-hunt-plan.md).

**How the sources were read.** The cloud session that wrote this could only use a web search tool; it could not open Google Patents, CNIPA, arXiv, GitHub pages or kling.ai directly (the network blocked them). So most entries below are based on **search-result text**, not on reading the full page. Each entry says which. All were retrieved on 2026-10-09.

## 1. Short answer

- **No public source says how Kling embeds its watermark.** We found no Kuaishou patent, no Kuaishou paper and no Kling technical note that describes the domain, frequencies, colour channel, strength, payload or robustness of a Kling image watermark.
- **The rules do not require a pixel watermark.** Chinese rules make the metadata label mandatory and only *encourage* a digital watermark.
- **Kling says it has one anyway.** Its own page claims an imperceptible watermark in images and videos that survives compression, editing and resharing.
- So the tests have to be **guided guesses**: we test the families of methods that are common, cheap to deploy, and match the word "blind watermark", and we use positive controls so a negative result means something.

## 2. Sources and what they say about the method

### 2.1 Rules and standards

| Source (date) | What it says | About HOW (domain, channel, strength, payload, robustness) | Read from |
|---|---|---|---|
| CAC et al., *Measures for Labeling AI-Generated Synthetic Content*, Art. 5 (issued 2025-03-14, in force 2025-09-01). [cac.gov.cn](https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm), [Xinhua copy](https://www.news.cn/politics/20250314/75107e1e6566404f8471559a8fb34158/c.html) | Metadata implicit labels are **required**. The state **encourages** ("鼓励") providers to add implicit labels such as digital watermarks inside the content. | Nothing about the method. | Search snippets |
| CAC press Q&A on the Measures (2025-03-14). [cac.gov.cn](https://www.cac.gov.cn/2025-03/14/c_1743654685896173.htm) | Implicit labels in text and **digital watermarks in multimedia files are not mandatory for now**, because of technical difficulty and cost. | Nothing about the method. | Search snippets |
| GB 45438-2025, *Cybersecurity technology - Labeling method for AI-generated synthetic content* (published early 2025 - one interpretation gives 2025-02-28 - in force 2025-09-01). Interpretations: [Zhihu](https://zhuanlan.zhihu.com/p/1891085128140293464), [ZJU notice](https://icsr.zju.edu.cn/2025/0317/c70143a3027668/page.htm) | Implicit labels are split into **file-metadata implicit labels** and **content implicit labels (for example digital watermarks)**. The metadata fields are the ones Kling uses (`Label`, `ContentProducer`, `ProduceID`, ...). | Interpretations describe content implicit labels only by example ("digital watermark"); no algorithm, domain or payload was found. The full text was not read. | Search snippets |
| TC260-PG-20233A, *Practice Guide - Labeling method for generative AI service content* (adopted 2023-08-25, non-mandatory). [Digital Policy Alert](https://digitalpolicyalert.org/change/6792-tc-260-practice-guide-to-cybersecurity-standards-on-generative-artificial-intelligence-service-content-identification-method), [Covington](https://www.insideprivacy.com/artificial-intelligence/labeling-of-ai-generated-content-new-guidelines-released-in-china/), [Zhihu summary](https://zhuanlan.zhihu.com/p/18470506373) | Lists five label types for generated content: display-area labels, prompt text, **hidden watermarks** (images, video, audio), file metadata, and special-scenario labels. | A law-firm summary says watermarking technology was "relatively immature". No method details found. | Search snippets |
| TC260 guide on **metadata** implicit labels for image files (adopted 2025-08-28), one of six guides published then. [Digital Policy Alert](https://digitalpolicyalert.org/event/33153-tc260-adopted-guidelines-on-identification-methods-for-ai-generated-synthetic-image-content), [secrss](https://www.secrss.com/articles/82518) | How to write the metadata label into HEIF/HEIC, JPEG, PNG, TIFF, WebP and GIF. | Metadata only; not a pixel watermark. | Search snippets |
| TC260 guide, *Service provider coding rules* (2025-03). [TC260 monthly report](https://www.tc260.org.cn/tc260/xwdt1/202504/c8ba62856cb44db5bf7cf6e12ac1af75.shtml), [secrss](https://www.secrss.com/articles/76654) | Defines the provider code. This explains Kling IMAGE 3.0's `0011` + USCC + `10100` producer field. | Metadata only. | Search snippets |
| CAICT (China Academy of Information and Communications Technology) | **Nothing found** about a watermark evaluation or test specification for AIGC implicit labels. | - | Searches returned no CAICT document |
| Zhejiang University GCmark platform, presented as a companion platform for GB 45438 (2025-03-17). [ZJU](https://icsr.zju.edu.cn/2025/0317/c70143a3027668/page.htm) | A labeling and detection platform from a university lab. | A search snippet says its watermark uses image semantic information plus adversarial training and randomized smoothing (a learned method). **Not linked to Kling.** | Search snippets |

### 2.2 Kling / Kuaishou

| Source (date) | What it says | About HOW | Read from |
|---|---|---|---|
| Kling, [AI Content Detection](https://kling.ai/docs/ai-content-detection) (retrieved 2026-10-09; also quoted in [forensic-audit-2026-10-09.md](forensic-audit-2026-10-09.md)) | "An imperceptible watermark and metadata are embedded in images and videos", "remaining traceable through compression, editing, and resharing", "aligned with open content-provenance standards (e.g. C2PA)". | **Robustness claim only** (compression, editing, resharing). Nothing on domain, channel, strength or payload. | Search snippet + owner's earlier reading |
| Kling detector, live API response (owner's browser session, 2026-10-09; see the audit) | Two checks: `AIGC_METADATA` and `BLIND_WATERMARK`. | The name "blind watermark" (Chinese 盲水印) usually means a watermark that is read **without the original image**. It says nothing more about the method. | Our own observation |
| Kuaishou / Beijing Dajia Internet Information Technology Co., Ltd. patents. Searched Google Patents, Justia and Patsnap for 北京快手科技有限公司 and 北京达佳互联信息技术有限公司 (Kuaishou's main patent filer; [Patsnap](https://discovery.patsnap.com/company/beijing-dajia-internet-information-technology/) lists about 11,000 patents) with 水印 / watermark | **No watermark-embedding patent by either company was found.** | - | Search snippets |
| Unverified leads (assignee not visible in search results) | US 11,869,112 "Watermark embedding method and apparatus, terminal, and storage medium" ([USPTO PDF](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11869112)); US 12,579,598 "Embedding and extracting watermark in video data", priority CN 202010906543.5 filed 2020-09-01 ([USPTO PDF](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12579598)); CN110322386A, a video watermark *identification* patent (2018 priority) listed under Dajia on a Google Patents citation list. | Not known. The CN patent appears to be about **recognising** visible logos in videos, not embedding. These need checking on Google Patents or CNIPA from a normal network. | Search snippets |
| Kuaishou research papers | **No watermarking paper with Kuaishou authors was found.** The Kling-MotionControl technical report ([arXiv 2603.03160](https://arxiv.org/html/2603.03160v1), 2026-03) mentions watermarking only as a safeguard it supports. | - | Search snippets |

### 2.3 Related open research (not Kuaishou)

| Source (date) | Why it matters | About HOW |
|---|---|---|
| SIGMark, ICLR 2026 ([arXiv 2603.02882](https://arxiv.org/abs/2603.02882), 2026-03-03; [code](https://github.com/JeremyZhao1998/SIGMark-release)). Authors Xinjie Zhu, Zijing Zhao, Hui Jin, Qingxiao Guo, Yilong Ma, Yunhao Wang, Xiaobing Guo, Weifeng Zhang; affiliations not seen. | In-generation video watermark with blind extraction for video diffusion models with causal 3D VAEs; cites Kling as an example. | The mark is put into the generation process (latent noise); extraction needs the model. **We cannot test this kind of mark without Kling's model.** |
| VideoShield, ICLR 2025 ([arXiv 2501.14195](https://arxiv.org/abs/2501.14195)) | In-generation video watermark; cites Kling. | Same class as above. |
| Video Seal, Meta ([arXiv 2412.09492](https://arxiv.org/abs/2412.09492), 2024-12) | Open post-hoc video watermark with public weights. | Learned embedder on luma at 256 px, 256-bit payload, made to survive H.264. **Testable** (`audit.py video`). |
| guofei9987/blind_watermark (PyPI `blind-watermark` 0.4.4, source read 2026-10-09) | The best-known open-source Chinese "盲水印" library. | Haar DWT → LL band → 4x4 blocks → DCT → SVD; the largest singular value is quantized with step `d1 = 36` (second with `d2 = 20`) in **Y, U and V**; bits repeat over all blocks; a password shuffles the DCT coefficients. **Testable without the password** (section 4). |
| invisible-watermark 0.2.0 (Stable Diffusion's default watermark library; source read 2026-10-09) | Widely copied. | `dwtDct`: Haar DWT LL of the **U** channel, 4x4 blocks, largest-magnitude value quantized with step 36. `dwtDctSvd`: same with the largest singular value. `rivaGan`: a learned 32-bit video watermark (ONNX models included). **All testable.** |

## 3. Facts and guesses

**Facts** (from the sources or our own measurements):

1. Chinese rules require the metadata label and only encourage a pixel watermark.
2. Kling claims an imperceptible watermark in images and videos that survives compression, editing and resharing.
3. Kling's detector runs a check called `BLIND_WATERMARK`; it returned `FAILED` on every submission we made.
4. No Kuaishou patent or paper describing the method was found.
5. Our earlier tests found no fixed pattern, no LSB scheme and none of SynthID, TrustMark, Watermark Anything or invisible-watermark dwtDct; flat regions of 105 plain IMAGE 3.0 images are untouched.

**Guesses** (reasoned, not proven):

1. **"Blind watermark" is a description, not a product name.** In Chinese industry it usually means a watermark read without the original, often a DWT/DCT/SVD frequency-domain method (as in `blind_watermark`) or a learned encoder/decoder.
2. **A claim of surviving "compression, editing and resharing" fits a learned (deep-network) watermark best.** Classic quantization schemes break under strong JPEG or video compression (our own control: blind_watermark survives H.264 at crf 18 but not crf 28).
3. **If the mark skips flat areas**, it is content-adaptive (masked by local texture). Our flat-image tests then say nothing, and tests must focus on textured images.
4. **The mark may be added before the 2x upscale.** Kling 2K images look like 2x-upscaled 1K images. A mark added at 1K would then live at half resolution; our scan therefore also looks one wavelet level down (the image at half size).
5. **An in-generation (latent-noise) watermark** like SIGMark or Tree-Ring is possible for Kling's own models; it cannot be found without the model, so only Kling's detector can confirm it.

## 4. What the new tests target

| Family | Why it is a candidate | Test | Can a negative rule it out? |
|---|---|---|---|
| Quantization (QIM) on DWT-DCT / DWT-DCT-SVD blocks: `blind_watermark`, invisible-watermark `dwtDct`/`dwtDctSvd`, most textbook 盲水印 | Cheap, common in Chinese tooling, "blind" | `audit.py qim`: key-free lattice scan. Quantized values all sit on a grid with step `d`; the scan finds that grid without knowing the key or message. Covers Y/U/V, two YUV conventions, DWT level 1 and level 2 (pre-upscale), steps 2.5-120. | **Yes**, for marks that quantize those block values with a fixed step and were not re-processed afterwards. **Not** for keyed dither (a secret offset per block), steps of exactly 8/3, 4, 16/3, 8, 16 or 32 (ignored to avoid integer-grid false alarms), or marks destroyed by later JPEG/video compression. |
| Public learned watermarks: RivaGAN, StegaStamp, HiDDeN | Easy to deploy from open code | `audit.py decoders`: does every Kling image decode to the same message, compared with PNG controls? | Only for those exact public weights. A company would normally train its own. |
| VideoSeal (video) | Open, built for H.264 robustness | `audit.py video`: VideoSeal detection bit and message test on frames | Only for the public VideoSeal 1.0 weights. |
| In-house learned or in-generation marks | Best fit to the robustness claim | No offline test possible | No. Only Kling's own detector (see the decisive experiment in the audit). |

Every test has a positive control on synthetic images (`audit.py controls`). Results of the controls run in the cloud on 2026-10-09:

| Control | Result |
|---|---|
| Clean synthetic images | not flagged (0/2) |
| invisible-watermark dwtDct, dwtDctSvd (step 36 and 12) | flagged 2/2 each |
| blind_watermark default mode, with its password shuffle | flagged 2/2 without knowing the password |
| dwtDctSvd at half size, then 2x upscale | flagged 2/2 (found at DWT level 2) |
| dwtDctSvd, then JPEG q90 | flagged 2/2 |
| Clean image saved as JPEG q75 | not flagged; lattice correctly blamed on JPEG |
| RivaGAN | bit accuracy 0.97; fixed-message test T = 25.9 (marked) vs 1.4 (clean) |
| Video pipeline (RivaGAN on frames, lossless and mp4v) | bit accuracy 1.00 |
| QIM on H.264 frames | clean clip not flagged; blind_watermark clip flagged at crf 18, lost at crf 28 |
| StegaStamp, HiDDeN | skipped: no weights in the cloud (owner supplies ONNX files) |
| VideoSeal | skipped: weights host not reachable from the cloud (runs locally) |
