# Paper 2 same-image ROI confirmation

All 306 records and 51 first-sample byte archives passed; six repeats per cell, one physical session.

Primary: request-to-selected-residual-publication service time; not rendering/display.

| Sparse equal-mask mean | Full raster | Outer bounding box | Merged rectangles |
|---|---:|---:|---:|
| ms | 114.873642 | 103.476320 | 96.156529 |

Ratios of mean service times: {"full_over_outer": 1.1101442484189392, "full_over_merged": 1.1946525394544232, "outer_over_merged": 1.0761237029835}

| Workload | Tiles | Full ms | Outer ms | Merged ms | Full/merged |
|---|---:|---:|---:|---:|---:|
| empty_control_0 | 0 | 0.159274 | 0.159263 | 0.159249 | 1.000160 |
| dense_control_0 | 60 | 309.887607 | 309.859860 | 309.940644 | 0.999829 |
| clustered_rectangles_10 | 6 | 57.493713 | 32.434864 | 32.423392 | 1.773217 |
| clustered_rectangles_50 | 15 | 99.532105 | 79.280944 | 79.305726 | 1.255043 |
| clustered_rectangles_90 | 30 | 167.577223 | 156.390676 | 156.410180 | 1.071396 |
| scattered_random_10 | 7 | 65.397257 | 62.495368 | 39.777340 | 1.644083 |
| scattered_random_50 | 17 | 116.212275 | 116.240132 | 95.067983 | 1.222412 |
| scattered_random_90 | 31 | 184.957121 | 184.936754 | 171.752282 | 1.076883 |
| adversarial_checkerboard_10 | 8 | 70.267448 | 67.637799 | 45.336754 | 1.549900 |
| adversarial_checkerboard_50 | 20 | 132.127964 | 122.992827 | 112.927877 | 1.170021 |
| adversarial_checkerboard_90 | 30 | 183.926670 | 183.913445 | 169.454023 | 1.085408 |
| deadline_truncated_prefix_10 | 5 | 52.941634 | 27.774052 | 28.008823 | 1.890177 |
| deadline_truncated_prefix_50 | 17 | 109.523205 | 96.205171 | 93.761491 | 1.168104 |
| deadline_truncated_prefix_90 | 24 | 143.651284 | 135.043340 | 129.742370 | 1.107204 |
| moving_disocclusion_band_10 | 8 | 67.597817 | 44.061937 | 44.035273 | 1.535083 |
| moving_disocclusion_band_50 | 18 | 112.925697 | 95.211853 | 95.219922 | 1.185946 |
| moving_disocclusion_band_90 | 28 | 158.973211 | 147.525640 | 149.124500 | 1.066044 |

All per-cell ranges, standard deviations, stage times, traffic and regressions are in summary.json.

Conventional cropping is established. This supports an exact, commit-safe integration and traversal trade-off, not a new sparse primitive, area/energy win, cross-application result or comparison against a purpose-built optimized conventional accelerator.
