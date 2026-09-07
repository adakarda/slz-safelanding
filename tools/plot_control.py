#!/usr/bin/env python3
"""Render the two poster figures for the control chapter.

Numbers come from docs/TEZ_NOTLARI.md rather than from a live run: they are the
medians of repeated flights, and a figure that quietly redraws itself from
whatever happened to run last is a figure nobody can check against the text.
Update them here and in the document together.

  tools/plot_control.py [OUT_DIR]     -> kontrol_bant.png, kontrol_dagilim.png
"""
import sys
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Figure 1: tracking error by altitude band, open loop vs closed (docs 2.3).
BANDS = ['10+ m', '5-10 m', '2-5 m', '0-2 m']
OPEN = [-0.51, -0.06, -0.37, -0.15]
CLOSED = [-0.09, -0.01, 0.01, -0.14]

# Figure 2: RMS spread over three flights per arm (docs 2.6).
ARMS = ['Acik cevrim', 'Elle ayarli PI', 'Turetilmis\n(Kp 0, Ki 1.39)']
RMS = [[0.322, 0.323, 1.829], [0.190, 0.201, 0.206], [0.186, 0.197, 0.214]]


def band_figure(path):
    x = np.arange(len(BANDS))
    w = 0.38
    fig, ax = plt.subplots(figsize=(6.4, 3.4), dpi=200)
    ax.bar(x - w / 2, OPEN, w, label='Acik cevrim (ust sinir)', color='#c44e52')
    ax.bar(x + w / 2, CLOSED, w, label='Kapali cevrim (referans)',
           color='#4c72b0')
    ax.axhline(0, color='black', lw=0.8)
    ax.set_xticks(x, BANDS)
    ax.set_ylabel('Takip hatasi (gerceklesen - komut) [m/s]')
    ax.set_title('Dikey hiz takip hatasi, irtifa bandina gore')
    ax.legend(frameon=False, fontsize=8)
    ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def spread_figure(path):
    fig, ax = plt.subplots(figsize=(5.2, 3.4), dpi=200)
    for i, vals in enumerate(RMS):
        ax.scatter([i] * len(vals), vals, s=44, color='#4c72b0', zorder=3)
        ax.plot([i - 0.16, i + 0.16], [np.median(vals)] * 2, color='#c44e52',
                lw=2, zorder=4)
    ax.set_xticks(range(len(ARMS)), ARMS, fontsize=8)
    ax.set_ylabel('RMS takip hatasi [m/s]')
    ax.set_title('Ucer ucus: ortanca (kirmizi) ve tek tek kosular')
    # Log scale, because the open-loop outlier is an order of magnitude out and
    # hiding it would remove the whole point of the figure.
    ax.set_yscale('log')
    ax.set_yticks([0.2, 0.3, 0.5, 1.0, 2.0])
    ax.get_yaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    # Log minor ticks come with their own scientific labels, which collide
    # with the plain ones above.
    ax.get_yaxis().set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.spines[['top', 'right']].set_visible(False)
    ax.annotate('inmeyi birakip asili kaldi,\ndokunma siteden 3.4 m',
                xy=(0, 1.829), xytext=(0.35, 1.5), fontsize=7,
                arrowprops=dict(arrowstyle='->', lw=0.8))
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else '/tmp'
    os.makedirs(out, exist_ok=True)
    a = os.path.join(out, 'kontrol_bant.png')
    b = os.path.join(out, 'kontrol_dagilim.png')
    band_figure(a)
    spread_figure(b)
    print(f'yazildi: {a}')
    print(f'yazildi: {b}')


if __name__ == '__main__':
    main()
