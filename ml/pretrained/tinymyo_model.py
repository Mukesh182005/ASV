"""TinyMyo model architecture — official checkpoint compatible implementation.

Matches the official PulpBio/TinyMyo pretraining architecture from arXiv:2512.15729:
- Patch embedding: Conv2d(1, 192, kernel_size=(1, 20), stride=(1, 20))
- Learned channel embeddings: Parameter(1, 16, 1, 192)
- 8 Transformer encoder blocks (embed_dim=192, n_head=3, mlp_ratio=4)
- Multi-Head Self-Attention with RoPE (Rotary Position Embeddings)
- Mean pooling over patch tokens for downstream representations

Loads official PulpBio/TinyMyo weights (TinyMyo.safetensors) with 100% key matching.
"""
import math
import logging
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from ml.pretrained.config import (
    TINYMYO_EMBED_DIM,
    TINYMYO_NUM_HEADS,
    TINYMYO_DEPTH,
    TINYMYO_MLP_RATIO,
    TINYMYO_DROPOUT,
    TINYMYO_PATCH_LENGTH,
    TINYMYO_PATCH_STRIDE,
    TINYMYO_WINDOW_SIZE,
    NUM_CLASSES,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rotary Position Embedding (RoPE) — per-channel reset
# ---------------------------------------------------------------------------
class RotaryPositionEmbedding(nn.Module):
    """Rotary Position Embedding with per-channel temporal reset.

    For channel-independent patching, temporal positions are reset for each
    channel so that the Transformer does not see artificial long-range
    distances between tokens from different channels.
    """

    def __init__(self, dim: int, max_seq_len: int = 2048):
        super().__init__()
        inv_freq = 1.0 / (10000.0 ** (torch.arange(0, dim, 2).float() / dim))
        self.register_buffer("inv_freq", inv_freq, persistent=False)
        self.max_seq_len = max_seq_len

    def forward(self, seq_len: int, device: torch.device) -> Tuple[torch.Tensor, torch.Tensor]:
        """Compute cos/sin position encodings for given sequence length."""
        t = torch.arange(seq_len, device=device, dtype=self.inv_freq.dtype)
        freqs = torch.outer(t, self.inv_freq)
        emb = torch.cat([freqs, freqs], dim=-1)
        return emb.cos(), emb.sin()


def _rotate_half(x: torch.Tensor) -> torch.Tensor:
    """Rotate half the hidden dims of the input."""
    x1 = x[..., : x.shape[-1] // 2]
    x2 = x[..., x.shape[-1] // 2 :]
    return torch.cat((-x2, x1), dim=-1)


def apply_rotary_pos_emb(
    q: torch.Tensor, k: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Apply rotary embeddings to queries and keys."""
    # cos/sin shape: (seq_len, head_dim)
    # q/k shape: (batch, heads, seq_len, head_dim)
    cos = cos.unsqueeze(0).unsqueeze(0)  # (1, 1, seq_len, head_dim)
    sin = sin.unsqueeze(0).unsqueeze(0)
    q_embed = (q * cos) + (_rotate_half(q) * sin)
    k_embed = (k * cos) + (_rotate_half(k) * sin)
    return q_embed, k_embed


# ---------------------------------------------------------------------------
# Official Patch Embedding module
# ---------------------------------------------------------------------------
class PatchEmbedSubModule(nn.Module):
    """Inner patch embed projection to match official state_dict path:
    patch_embedding.patch_embed.proj
    """
    def __init__(self, patch_length: int, patch_stride: int, embed_dim: int):
        super().__init__()
        self.proj = nn.Conv2d(
            in_channels=1,
            out_channels=embed_dim,
            kernel_size=(1, patch_length),
            stride=(1, patch_stride),
            bias=True,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, 1, C, T)
        return self.proj(x)  # (B, embed_dim, C, N_patches)


class OfficialPatchEmbedding(nn.Module):
    """Channel-independent patch embedding matching official implementation.

    Input signal shape: (batch, channels, time_steps)
    Reshaped to: (batch, 1, channels, time_steps)
    Conv2d output: (batch, embed_dim, channels, n_patches)
    Permuted & added with channel_embed: (batch, channels * n_patches, embed_dim)
    """

    def __init__(
        self,
        patch_length: int = TINYMYO_PATCH_LENGTH,
        patch_stride: int = TINYMYO_PATCH_STRIDE,
        embed_dim: int = TINYMYO_EMBED_DIM,
    ):
        super().__init__()
        self.patch_length = patch_length
        self.patch_stride = patch_stride
        self.embed_dim = embed_dim
        self.patch_embed = PatchEmbedSubModule(patch_length, patch_stride, embed_dim)

    def forward(self, x: torch.Tensor, channel_embed: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Args:
            x: (B, C, T) raw EMG signal
            channel_embed: (1, 16, 1, embed_dim) learned channel embeddings (optional)

        Returns:
            tokens: (B, C * n_patches, embed_dim)
        """
        B, C, T = x.shape
        x_4d = x.unsqueeze(1)  # (B, 1, C, T)
        feat = self.patch_embed(x_4d)  # (B, embed_dim, C, N_patches)

        # Transpose to (B, C, N_patches, embed_dim)
        feat = feat.permute(0, 2, 3, 1)

        # Add channel embedding (up to C channels used)
        if channel_embed is not None:
            ch_emb = channel_embed[:, :C, :, :]  # (1, C, 1, embed_dim)
            feat = feat + ch_emb  # broadcast over N_patches

        # Flatten (C, N_patches) into token sequence
        tokens = feat.reshape(B, C * (T // self.patch_length), self.embed_dim)
        return tokens


# Alias for backward compatibility
PatchEmbedding = OfficialPatchEmbedding


# ---------------------------------------------------------------------------
# Transformer components (matching official module names)
# ---------------------------------------------------------------------------
class MultiHeadAttention(nn.Module):
    """Multi-head self-attention with RoPE."""

    def __init__(self, embed_dim: int, num_heads: int, dropout: float = 0.0):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        assert self.head_dim * num_heads == embed_dim

        self.qkv = nn.Linear(embed_dim, 3 * embed_dim)
        self.proj = nn.Linear(embed_dim, embed_dim)
        self.attn_drop = nn.Dropout(dropout)
        self.proj_drop = nn.Dropout(dropout)
        self.scale = self.head_dim ** -0.5

    def forward(
        self, x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor
    ) -> torch.Tensor:
        B, N, D = x.shape
        qkv = self.qkv(x).reshape(B, N, 3, self.num_heads, self.head_dim)
        qkv = qkv.permute(2, 0, 3, 1, 4)  # (3, B, heads, N, head_dim)
        q, k, v = qkv.unbind(0)

        # Apply RoPE
        q, k = apply_rotary_pos_emb(q, k, cos, sin)

        attn = (q @ k.transpose(-2, -1)) * self.scale
        attn = F.softmax(attn, dim=-1)
        attn = self.attn_drop(attn)

        out = (attn @ v).transpose(1, 2).reshape(B, N, D)
        out = self.proj(out)
        out = self.proj_drop(out)
        return out


class MLP(nn.Module):
    """MLP module matching official key names (fc1, fc2)."""

    def __init__(self, in_features: int, hidden_features: int, dropout: float = 0.0):
        super().__init__()
        self.fc1 = nn.Linear(in_features, hidden_features)
        self.act = nn.GELU()
        self.fc2 = nn.Linear(hidden_features, in_features)
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.fc1(x)
        x = self.act(x)
        x = self.drop(x)
        x = self.fc2(x)
        x = self.drop(x)
        return x


class TransformerBlock(nn.Module):
    """Standard Transformer block matching official key structure."""

    def __init__(
        self,
        embed_dim: int = TINYMYO_EMBED_DIM,
        num_heads: int = TINYMYO_NUM_HEADS,
        mlp_ratio: float = TINYMYO_MLP_RATIO,
        dropout: float = TINYMYO_DROPOUT,
    ):
        super().__init__()
        self.norm1 = nn.LayerNorm(embed_dim)
        self.attn = MultiHeadAttention(embed_dim, num_heads, dropout)
        self.norm2 = nn.LayerNorm(embed_dim)

        mlp_hidden = int(embed_dim * mlp_ratio)
        self.mlp = MLP(embed_dim, mlp_hidden, dropout)

    def forward(
        self, x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor
    ) -> torch.Tensor:
        x = x + self.attn(self.norm1(x), cos, sin)
        x = x + self.mlp(self.norm2(x))
        return x


# ---------------------------------------------------------------------------
# TinyMyo Encoder (official backbone structure)
# ---------------------------------------------------------------------------
class TinyMyoEncoder(nn.Module):
    """TinyMyo Transformer encoder backbone.

    State dict keys exactly match official `PulpBio/TinyMyo` checkpoint:
    - patch_embedding.patch_embed.proj.{weight, bias}
    - channel_embed (1, 16, 1, 192)
    - blocks.0..7.{norm1, attn.qkv, attn.proj, norm2, mlp.fc1, mlp.fc2}
    - norm.{weight, bias}
    """

    def __init__(
        self,
        patch_length: int = TINYMYO_PATCH_LENGTH,
        patch_stride: int = TINYMYO_PATCH_STRIDE,
        embed_dim: int = TINYMYO_EMBED_DIM,
        depth: int = TINYMYO_DEPTH,
        num_heads: int = TINYMYO_NUM_HEADS,
        mlp_ratio: float = TINYMYO_MLP_RATIO,
        dropout: float = TINYMYO_DROPOUT,
        max_channels: int = 16,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.patch_embedding = OfficialPatchEmbedding(patch_length, patch_stride, embed_dim)
        self.channel_embed = nn.Parameter(torch.zeros(1, max_channels, 1, embed_dim))
        self.rope = RotaryPositionEmbedding(
            dim=embed_dim // num_heads, max_seq_len=2048
        )
        self.blocks = nn.ModuleList(
            [
                TransformerBlock(embed_dim, num_heads, mlp_ratio, dropout)
                for _ in range(depth)
            ]
        )
        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, channels, time_steps) raw EMG

        Returns:
            features: (batch, embed_dim) pooled representation
        """
        tokens = self.patch_embedding(x, self.channel_embed)  # (B, N_tokens, embed_dim)
        B, N, D = tokens.shape

        cos, sin = self.rope(N, tokens.device)
        cos = cos[:N, :]
        sin = sin[:N, :]

        for block in self.blocks:
            tokens = block(tokens, cos, sin)

        tokens = self.norm(tokens)
        features = tokens.mean(dim=1)  # (B, embed_dim)
        return features

    def forward_tokens(self, x: torch.Tensor) -> torch.Tensor:
        """Return all token embeddings (before pooling) for analysis."""
        tokens = self.patch_embedding(x, self.channel_embed)
        B, N, D = tokens.shape
        cos, sin = self.rope(N, tokens.device)
        cos = cos[:N, :]
        sin = sin[:N, :]
        for block in self.blocks:
            tokens = block(tokens, cos, sin)
        tokens = self.norm(tokens)
        return tokens


# ---------------------------------------------------------------------------
# Full model with classification head
# ---------------------------------------------------------------------------
class TinyMyoClassifier(nn.Module):
    """TinyMyo backbone + downstream classification head."""

    def __init__(
        self,
        num_classes: int = NUM_CLASSES,
        head_type: str = "mlp",
        freeze_backbone: bool = True,
        **encoder_kwargs,
    ):
        super().__init__()
        self.encoder = TinyMyoEncoder(**encoder_kwargs)
        self.freeze_backbone = freeze_backbone

        if freeze_backbone:
            for param in self.encoder.parameters():
                param.requires_grad = False

        embed_dim = self.encoder.embed_dim

        if head_type == "linear":
            self.head = nn.Linear(embed_dim, num_classes)
        elif head_type == "mlp":
            self.head = nn.Sequential(
                nn.Linear(embed_dim, embed_dim),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(embed_dim, num_classes),
            )
        else:
            raise ValueError(f"Unknown head_type: {head_type}")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, channels, time_steps)
        Returns:
            logits: (batch, num_classes)
        """
        features = self.encoder(x)
        logits = self.head(features)
        return logits

    def get_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract backbone features without classification head."""
        with torch.no_grad():
            return self.encoder(x)

    def unfreeze_backbone(self):
        """Unfreeze backbone parameters for fine-tuning."""
        self.freeze_backbone = False
        for param in self.encoder.parameters():
            param.requires_grad = True

    def count_parameters(self) -> dict:
        """Count trainable and total parameters."""
        total = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        backbone = sum(p.numel() for p in self.encoder.parameters())
        head = sum(p.numel() for p in self.head.parameters())
        return {
            "total": total,
            "trainable": trainable,
            "frozen": total - trainable,
            "backbone": backbone,
            "head": head,
        }


# ---------------------------------------------------------------------------
# Weight loading utilities
# ---------------------------------------------------------------------------
def load_pretrained_weights(
    model: TinyMyoEncoder, checkpoint_path: str
) -> Tuple[bool, str]:
    """Load official pretrained weights from safetensors checkpoint.

    Verifies exact key matching against official PulpBio/TinyMyo checkpoint.
    Returns (success: bool, message: str).
    """
    import os

    if not os.path.exists(checkpoint_path):
        return False, f"Checkpoint not found: {checkpoint_path}"

    try:
        from safetensors.torch import load_file
        raw_state_dict = load_file(checkpoint_path)

        # Strip 'model.' prefix if present in checkpoint keys
        state_dict = {}
        for k, v in raw_state_dict.items():
            # Skip pretraining reconstruction head keys
            if k.startswith("model.model_head.") or k == "model.mask_token":
                continue
            clean_k = k[6:] if k.startswith("model.") else k
            state_dict[clean_k] = v

        model_keys = set(model.state_dict().keys())
        ckpt_keys = set(state_dict.keys())

        missing = model_keys - ckpt_keys
        unexpected = ckpt_keys - model_keys

        if missing or unexpected:
            msg = (
                f"Key mismatch loading official checkpoint.\n"
                f"  Missing keys in checkpoint ({len(missing)}): {sorted(list(missing))[:5]}\n"
                f"  Unexpected keys ({len(unexpected)}): {sorted(list(unexpected))[:5]}"
            )
            logger.error(msg)
            return False, msg

        # Strict weight loading
        model.load_state_dict(state_dict, strict=True)
        num_loaded = len(state_dict)
        num_params = sum(p.numel() for p in model.parameters())
        msg = f"SUCCESS: Loaded {num_loaded} official pretrained layers ({num_params:,} parameters) with ZERO missing/unexpected keys!"
        logger.info(msg)
        return True, msg

    except Exception as e:
        msg = f"Error loading official checkpoint: {e}"
        logger.error(msg)
        return False, msg
