# Pixel-pattern spike (2026-10-09)

Throwaway investigation. The analysis code was not kept; this note records the findings.

## Question

Does Kling embed a hidden pixel watermark in addition to the `AIGC` metadata label?

## Data

- 24 Kling IMAGE 2.1 PNGs, all 1536x2720 (2K, 9:16), generated on 2026-10-09 through the kling.ai website.
- 49 control images that are not from Kling: phone photos, screenshots, messaging-app JPEGs and downloaded images.

## Method

- **Noise residual:** luminance minus a Gaussian blur (sigma = 1.5). Clipped pixels (0 or 255) and the visible logo region (rows >= 2480, columns >= 1000) were masked. Each residual was normalized to unit standard deviation.
- **Fixed-pattern test (PRNU-style):** each Kling residual was correlated with the mean residual of the other 23 images (leave-one-out). Each control was correlated with the mean of all 24 over the overlapping top-left crop.
- **Spectra:** FFT of the mean residual and the average magnitude spectrum. Peaks were measured against a 9x9 local median.
- **Extra checks:** the same test per color channel (R, G, B), least-significant-bit agreement, 8-pixel JPEG blockiness, tile-seam profiles, and a deficit map of the plain-white image.

## Results

| Test | Kling | Controls | Reading |
|------|-------|----------|---------|
| Leave-one-out correlation, luminance | mean 0.0014, max 0.0078 | mean 0.0000, max 0.0038 | No strong fixed pattern |
| Same, after removing periodic grid (period <= 32 px) | mean 0.0004 | about 0 | The shared signal is mostly the periodic grid |
| Leave-one-out per channel (R, G, B) | mean 0.0017 to 0.0020 | about 0 | Same as luminance |
| Spectral peaks | All at multiples of 1/16 cycle per pixel (periods 2, 4, 8, 16 px) | - | Typical upscaler or VAE grid, not a keyed carrier |
| Peaks off that grid | Only leakage next to grid points | - | No SynthID-style carrier frequencies |
| LSB agreement between images (G channel) | 0.506 | - | Random, so no LSB mark |
| 8-px JPEG blockiness | Flat (0.97 to 1.03) | Phase 7 = 1.15 | Kling PNGs were never JPEG-compressed |
| Tile seams | Rows near 836, 1564, 2340 in the plain-white image; present in only 25-30% of images | - | Likely tiled 2K upscaling; too weak to rely on |

A deficit map of the plain-white image (kept locally, not published) shows the tile layout as rectangular blocks with seams.

## Conclusion

With 24 images, no hidden pixel watermark was detected. The `AIGC` tEXt metadata chunk is the only reliable label found. A weak pipeline fingerprint exists (a periodic grid with periods of 2 to 16 px). Many AI generators and JPEG compression produce similar grids, so it needs a proper false-positive evaluation before any use.

## Follow-up: two plain mid-tone images

Later the same day, two near-uniform images were obtained (prompt "Exact copy of the reference image..." with a flat reference image). Both are 1536x2720 PNG and both carry the `AIGC` label.

- Over the whole frame, the residuals of the two images correlate at 0.76 to 0.87. Excluding a 32 px border drops this to about 0.001. The shared signal is only a ragged edge artifact: in one image, 99.1% of the deviation energy sits in the outer 32 px.
- Inside a 96 px margin (logo region excluded), image 1 has exactly one value in R and one in G (94) across 100% of interior pixels, and 99.8% of B pixels share one value. Image 2 has 99.999% (R), 99.991% (G) and 94.2% (B) of pixels at a single value.
- A pixel-domain invisible watermark has to change pixel values across the image. A perfectly constant interior leaves no room for one, at least in R and G.

This is strong evidence that these outputs carry no invisible pixel watermark. Caveat: both images came from reference mode, which may use a different pipeline than plain text-to-image.

## Limits

Not finding a watermark does not prove there is none. A weaker spread-spectrum mark, a per-image keyed mark, or a mark used only in some modes (video, other resolutions) would need hundreds of samples. Only IMAGE 2.1 at 1536x2720 was tested.
