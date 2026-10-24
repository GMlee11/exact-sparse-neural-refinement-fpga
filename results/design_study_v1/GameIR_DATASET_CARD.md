---
license: mit
task_categories:
- image-to-image
- image-to-3d
language:
- en
pretty_name: GameIR
size_categories:
- 100B<n<1T
---
# GameIR

Image restoration techniques such as super-resolution and image synthesis are used in products like NVIDIA's DLSS but are less understood by the public when applied to gaming. This is due to a shortage of relevant ground-truth training data for gaming, which differs from typical content with its distinct, sharp low-resolution images.

In this case, we develop GameIR, a large-scale high-quality computer-synthesized ground-truth dataset to fill in the blanks, targeting at 2 different applications. 
- The first is super-resolution (SR) with deferred rendering, to support the gaming solution of rendering and transferring LR images only and restoring HR images on the client side. 
- The second is novel view synthesis (NVS), to support the multiview gaming solution of rendering and transferring part of the multiview frames and generating the remaining frames on the client side. 

In addition to the RGB frames, the GBuffers during the deferred rendering stage (i.e., segmentation maps, and depth maps) are also provided, which can be used to help restoration.

### Dataset Sources

- **Repository:** [GameIR](https://huggingface.co/datasets/LLLebin/GameIR)
- **Paper:** [More Information Needed]

## Dataset Details
GameIR is collected using CARLA, which provids 8 towns: Town01, Town02, Town03, Town04, Town05, Town06, Town07, and Town08. For each town, we collected two types of scenes: 
- the static scene: no other moving vehicles in the scene.
- the dynamic scene: some other moving vehicles in the scene. 

In addition, each town has many different spawn points, and we will randomly select them from the town to collect data.

### GameIR-SR: Dataset for Super-Resolution
| Dataset           | Full Dataset (train)| Full Dataset (test) | Mini Dataset (train) | Mini Dataset (test) |
| :-----------      | :-----------:       | :-----------:       | :-----------:        |   :-----------:     |
| Town              | static town {01-04, 06-08}, <br>dynamic town {01-04, 06-08} | static town 05, <br>dynamic town 05 |  static town {01-04, 06-08}, <br>dynamic town {01-04, 06-08} |          static town 05, <br>dynamic town 05          |
| Spawn Site        | 20                  | 20                  | 20                   | 20                  |
| Sampling Rate     | 100%                | 100%                | 10%                  | 10%                 |
| Resolution        | 1920x1440 / 960x720 | 1920x1440 / 960x720 | 1920x1440 / 960x720  | 1920x1440 / 960x720 |
| Data Path         | full_dataset/train/GameIR-SR  | full_dataset/test/GameIR-SR         | mini_dataset/train/GameIR-SR    | mini_dataset/test/GameIR-SR        |
| GBuffer           | ✓                   | ✓                   | ✓                    | ✓                   |
| Camera Parameters | ✓                   | ✓                   | ✓                    | ✓                   |

### GameIR-NVS: Dataset for Novel View Synthesis
| Dataset           | Full Dataset (train)| Full Dataset (test) | Mini Dataset (train) | Mini Dataset (test) |
| :-----------      | :-----------:       | :-----------:       | :-----------:        |   :-----------:     |
| Town              | static town {01-08} | static town {01-08} | static town {01-08}  | static town {01-08} |
| Spawn Site        | 20                  | 20                  | 2                    | 2                   |
| Sampling Rate     | 90% / 10%           | 10% / 90%           | 90% / 10%            | 10% / 90%           |
| Resolution        | 1920x1440           | 1920x1440           | 1920x1440            | 1920x1440           |
| Data Path         | full_dataset/train/GameIR-NVS  | full_dataset/test/GameIR-NVS        | mini_dataset/train/GameIR-NVS    | mini_dataset/test/GameIR-NVS       |
| GBuffer           | ✓                   | ✓                   | ✓                    | ✓                   |
| Camera Parameters | ✓                   | ✓                   | ✓                    | ✓                   |

## How to Download

[Use Hugging Face Command Line Interface (CLI)](https://huggingface.co/docs/huggingface_hub/guides/cli#huggingface-cli-download)

```
Download Entire Dataset

$ huggingface-cli download LLLebin/GameIR --repo-type dataset --local-dir .


Download Specified Folder

$ huggingface-cli download LLLebin/GameIR --repo-type dataset --include mini_dataset/train/* --local-dir .
```

[Use Git](https://huggingface.co/docs/hub/datasets-downloading#using-git)
```
$ git lfs install
$ git clone https://huggingface.co/datasets/LLLebin/GameIR
```

After download the dataset, you can use following codes to extract the files in each subfolder (take the mini_data/train/GameIR-SR as an example)：

```
$ cd mini_dataset/train/GameIR-SR
$ for tarfile in GameIR-SR-*.tar; do tar -xf "$tarfile"; done
```

## How to Use

- For GameIR-SR, please refer to [GameIR-SR_demo](https://huggingface.co/datasets/LLLebin/GameIR/blob/main/demo/sr_demo.ipynb)
- For GameIR-NVS, please refer to [GameIR-NVS_demo](https://huggingface.co/datasets/LLLebin/GameIR/blob/main/demo/nvs_demo.ipynb)

# Citation