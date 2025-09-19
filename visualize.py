import os
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from typing import Optional, Tuple

def render_voxels(
    alive: np.ndarray,  # [Z,Y,X] uint8
    rgb: np.ndarray,    # [3,Z,Y,X] uint8
    out_path: str,
    elev: int = 20,
    azim: int = 45,
    title: Optional[str] = None,
    alpha: float = 1.0,
    figsize: Optional[Tuple[float,float]] = None,
    dpi: Optional[int] = None
) -> None:
    """Render a 3D voxel plot with per-voxel facecolors from rgb."""
    zdim, ydim, xdim = alive.shape
    filled = alive.astype(bool)

    facecolors = np.zeros(filled.shape + (4,), dtype=np.float32)
    if filled.any():
        r = (rgb[0].astype(np.float32)/255.0)
        g = (rgb[1].astype(np.float32)/255.0)
        b = (rgb[2].astype(np.float32)/255.0)
        facecolors[...,0] = r
        facecolors[...,1] = g
        facecolors[...,2] = b
        facecolors[...,3] = alpha
        facecolors[~filled] = (0,0,0,0)

    fig = plt.figure(figsize=(8,8) if figsize is None else figsize)
    ax = fig.add_subplot(111, projection='3d')
    ax.voxels(filled, facecolors=facecolors, edgecolor=None)

    ax.set_xlim(0, xdim); ax.set_ylim(0, ydim); ax.set_zlim(0, zdim)
    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
    if title:
        ax.set_title(title)

    ax.view_init(elev=elev, azim=azim)
    plt.tight_layout()
    fig.savefig(out_path, dpi=(150 if dpi is None else dpi))
    plt.close(fig)

def render_slice_grid(
    alive: np.ndarray,
    rgb: np.ndarray,
    out_path: str,
    axis: int = 0
) -> None:
    """Render all slices along a given axis as a grid of 2D images."""
    dims = alive.shape
    n = dims[axis]
    cols = int(np.ceil(np.sqrt(n)))
    rows = int(np.ceil(n/cols))

    fig, axs = plt.subplots(rows, cols, figsize=(3*cols, 3*rows))
    axs = np.array(axs).reshape(rows, cols)

    for i in range(rows*cols):
        r = i//cols; c = i%cols
        ax = axs[r,c]
        ax.axis('off')
        if i < n:
            if axis == 0:
                sl_alive = alive[i]
                sl_rgb = rgb[:,i]
            elif axis == 1:
                sl_alive = alive[:,i,:]
                sl_rgb = rgb[:,:,i,:]
            else:
                sl_alive = alive[:,:,i]
                sl_rgb = rgb[:,:,:,i]
            color_img = np.stack([sl_rgb[0], sl_rgb[1], sl_rgb[2]], axis=-1).astype(np.uint8)
            mask = sl_alive==1
            img = np.zeros_like(color_img)
            img[mask] = color_img[mask]
            ax.imshow(img)
            ax.set_title(f"{['Z','Y','X'][axis]}={i}")
    plt.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
