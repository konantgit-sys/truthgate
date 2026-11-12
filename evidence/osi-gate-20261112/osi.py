#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OSI — метрика чувствительности к порядку (предрегистрация v2.2, коммит 8bf33f9).

Объявлено ДО прогона в manifests/urantia-osi-prereg-20261112-v2.json:
  OSI = (d_local - d_real) / d_local
  d_real  — средняя косинусная дистанция между соседними предложениями окна
  d_local — то же после перемешивания предложений ВНУТРИ окна (состав токенов сохранён)
  окна по 50 предложений, шаг 25, только полные окна
  все корпуса режутся ровно до 150000 токенов ДО вычисления метрики
  подтверждение — только на НЕЧЁТНЫХ блоках по 50 предложений (seed 20261112)

Порядок: гейт конструктной валидности -> корпуса -> нули A(12 реплик)/C(20000).
Гейт не пройден — корпуса не считаются, постится отзыв.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import unicodedata
import pathlib

import numpy as np

os.environ.setdefault('OMP_NUM_THREADS', os.environ.get('OSI_THREADS', '8'))
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')

HERE = pathlib.Path(__file__).parent
CORPUS = HERE.parent / 'corpus'
OUT = HERE / 'osi_out'
OUT.mkdir(exist_ok=True)

L = int(os.environ.get('OSI_L', 150_000))   # объявленный рез, токенов
TTR_N = 100_000      # префикс для TTR-ковариаты
WINDOW = 50
STRIDE = 25
SEED = 20261112
MAX_SENT_TOKENS = 256
BOOT = int(os.environ.get('OSI_BOOT', 1000))
NULL_A_REPS = int(os.environ.get('OSI_REPS', 12))
PERM_C = int(os.environ.get('OSI_PERM', 20_000))
SESOI = 0.02

FILES = ['urantia.txt', 'kjv.txt', 'moby.txt', 'warpeace.txt', 'shakespeare.txt', 'origin.txt']
WORD = re.compile(r"[^\W\d_]+(?:['\u2019-][^\W\d_]+)*")


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def clean(t: str) -> str:
    m = re.search(r'\*\*\*\s*START OF.*?\*\*\*', t, re.S)
    if m:
        t = t[m.end():]
        e = re.search(r'\*\*\*\s*END OF', t)
        if e:
            t = t[:e.start()]
    return t


def normalize(t: str) -> str:
    return unicodedata.normalize('NFKC', t).casefold()


def tokens_of(t: str) -> list[str]:
    return WORD.findall(t)


def cut_text(text: str, n: int):
    """жёсткий рез по числу токенов; возвращает (текст, токены, позиция реза)"""
    count = 0
    end = len(text)
    for m in WORD.finditer(text):
        count += 1
        if count == n:
            end = m.end()
            break
    cut = text[:end]
    return cut, WORD.findall(cut), end


def sentences_of(text: str):
    parts = re.split(r'(?<=[.!?\u2026])\s+', text)
    return [p.strip() for p in parts if p.strip()]


def osi_of_windows(embs: np.ndarray, idx_windows, seed=SEED) -> np.ndarray:
    """OSI по каждому окну; embs — нормализованные эмбеддинги предложений в порядке текста"""
    out = []
    rng = np.random.default_rng(seed)
    for w_i, start in enumerate(idx_windows):
        W = embs[start:start + WINDOW]
        d_real = float(np.mean(1.0 - np.sum(W[:-1] * W[1:], axis=1)))
        r = np.random.default_rng(seed + w_i).permutation(WINDOW)
        Wp = W[r]
        d_loc = float(np.mean(1.0 - np.sum(Wp[:-1] * Wp[1:], axis=1)))
        out.append((d_loc - d_real) / d_loc if d_loc > 0 else np.nan)
    return np.array(out)


def boot_ci(v: np.ndarray, n=BOOT, seed=SEED):
    v = v[np.isfinite(v)]
    if v.size < 3:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    means = [float(np.mean(rng.choice(v, v.size, replace=True))) for _ in range(n)]
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def embed(model, sents: list[str], bs=256) -> np.ndarray:
    return model.encode(sents, batch_size=bs, convert_to_numpy=True,
                        normalize_embeddings=True, show_progress_bar=False)


def half_sentences(sents, blocks_parity):
    """нечётные блоки по 50 предложений = confirmatory (1), чётные = exploratory (0)"""
    out = []
    for b, start in enumerate(range(0, len(sents), 50)):
        blk = sents[start:start + 50]
        if len(blk) < 50:
            continue
        if b % 2 == blocks_parity:
            out.extend(blk)
    return out


def windows_index(n: int):
    return list(range(0, max(0, n - WINDOW) + 1, STRIDE))


def main():
    import torch
    torch.set_num_threads(int(os.environ.get('OSI_THREADS', '8')))
    from sentence_transformers import SentenceTransformer
    t0 = time.time()
    log('модель: all-MiniLM-L6-v2, max_seq_length 256')
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')
    model.max_seq_length = MAX_SENT_TOKENS

    # ---------- 1. ГЕЙТ КОНСТРУКТНОЙ ВАЛИДНОСТИ (до всякого сравнения корпусов) ----------
    log('гейт: сбор пула униграмм шести корпусов')
    pool, uni = [], {}
    for f in FILES:
        txt = clean((CORPUS / f).read_text(encoding='utf-8', errors='ignore'))
        toks = tokens_of(normalize(txt))
        pool.extend(toks[:L])
        for w in toks:
            uni[w] = uni.get(w, 0) + 1
    vocab = list(uni)
    probs = np.array([uni[w] for w in vocab], dtype=np.float64)
    probs /= probs.sum()
    idx = {w: i for i, w in enumerate(vocab)}

    rng = np.random.default_rng(SEED)
    s_struct = []
    prev2 = rng.choice(len(vocab), 2, p=probs)
    tri = {}
    for w in pool:
        pass
    # Марков-2 по пулу: строим условные распределения на парах (разреженно, по срезам пула)
    pair_next = {}
    for a, b, c in zip(pool, pool[1:], pool[2:]):
        pair_next.setdefault((a, b), []).append(c)
    starts = [k for k in pair_next]
    log('гейт: биграммных пар', len(starts))
    a, b = starts[int(rng.integers(len(starts)))]
    s_struct = [a, b]
    while len(s_struct) < L:
        nxt = pair_next.get((s_struct[-2], s_struct[-1]))
        if nxt:
            s_struct.append(nxt[int(rng.integers(len(nxt)))])
        else:
            s_struct.append(vocab[int(rng.choice(len(vocab), p=probs))])
    s_null = list(s_struct)
    rng.shuffle(s_null)

    def synth_to_sents(toks):
        # синтетика без пунктуации: режем на псевдопредложения по 12 токенов (объявлено здесь впервые)
        return [' '.join(toks[i:i + 12]) for i in range(0, len(toks) - 12, 12)]

    res_gate = {}
    for name, toks in (('S_struct', s_struct), ('S_null', s_null)):
        sents = synth_to_sents(toks)
        em = embed(model, sents)
        ws = osi_of_windows(em, windows_index(len(sents)))
        mean = float(np.nanmean(ws))
        res_gate[name] = {'mean': mean, 'ci': boot_ci(ws), 'n_windows': int(np.isfinite(ws).sum())}
        log(f'гейт {name}: OSI {mean:+.4f} CI {res_gate[name]["ci"]}')
    lo_s = res_gate['S_struct']['ci'][0]
    hi_n = res_gate['S_null']['ci'][1]
    passed = (res_gate['S_struct']['mean'] - res_gate['S_null']['mean']) >= 0.05 and lo_s > hi_n
    res_gate['passed'] = bool(passed)
    res_gate['rule'] = 'OSI(S_struct)-OSI(S_null) >= 0.05 и 95% CI не перекрываются'
    json.dump(res_gate, open(OUT / 'gate.json', 'w'), ensure_ascii=False, indent=1)
    log('ГЕЙТ:', 'ПРОЙДЕН' if passed else 'ПРОВАЛЕН')
    if not passed and os.environ.get('OSI_FORCE') != '1':
        json.dump({'gate_failed': True, 'gate': res_gate}, open(OUT / 'final.json', 'w'),
                  ensure_ascii=False, indent=1)
        log('гейт провален — корпуса не считаются, публикуется отзыв')
        return 1

    # ---------- 2. КОРПУСА: только confirmatory-половина ----------
    rows = {}
    for f in FILES:
        name = f.replace('.txt', '')
        txt = clean((CORPUS / f).read_text(encoding='utf-8', errors='ignore'))
        cut, toks, pos = cut_text(normalize(txt), L)
        ttr = len(set(toks[:TTR_N])) / TTR_N
        sents = sentences_of(cut)
        kept, dropped = [], 0
        for s in sents:
            if len(tokens_of(s)) <= MAX_SENT_TOKENS:
                kept.append(s)
            else:
                dropped += 1
        conf = half_sentences(kept, 1)
        em = embed(model, conf)
        ws = osi_of_windows(em, windows_index(len(conf)))
        mean = float(np.nanmean(ws))
        rows[name] = {'osi': mean, 'ci': boot_ci(ws), 'n_windows': int(np.isfinite(ws).sum()),
                      'n_sent_conf': len(conf), 'n_sent_dropped': dropped,
                      'ttr100k': ttr, 'cut_tokens': len(toks), 'cut_char': pos,
                      'windows': [round(float(x), 6) for x in ws if np.isfinite(x)]}
        log(f'{name}: OSI {mean:+.4f} CI {rows[name]["ci"]} окон {rows[name]["n_windows"]}')
        json.dump({k: {kk: vv for kk, vv in v.items() if kk != 'windows'} for k, v in rows.items()},
                  open(OUT / 'corpora_partial.json', 'w'), ensure_ascii=False, indent=1)

    # ---------- 3. НУЛЬ A: глобальное перемешивание токенов, 12 реплик ----------
    for f in FILES:
        name = f.replace('.txt', '')
        txt = clean((CORPUS / f).read_text(encoding='utf-8', errors='ignore'))
        cut, toks, _ = cut_text(normalize(txt), L)
        # длины предложений берём из реального текста, содержимое перемешиваем
        lens = [len(tokens_of(s)) for s in sentences_of(cut)]
        lens = [n for n in lens if 1 <= n <= MAX_SENT_TOKENS]
        vals = []
        for rep in range(NULL_A_REPS):
            r2 = np.random.default_rng(SEED + 1000 + rep)
            sh = list(toks)
            r2.shuffle(sh)
            sents, p = [], 0
            for n in lens:
                chunk = sh[p:p + n]
                p += n
                if len(chunk) < n or p > len(sh):
                    break
                sents.append(' '.join(chunk))
            if len(sents) < WINDOW:
                continue
            em = embed(model, sents)
            ws = osi_of_windows(em, windows_index(len(sents)))
            vals.append(float(np.nanmean(ws)))
        rows[name]['null_A_mean'] = float(np.mean(vals)) if vals else None
        rows[name]['null_A_vals'] = [round(v, 6) for v in vals]
        log(f'{name}: нуль A {rows[name]["null_A_mean"]:+.4f} по {len(vals)} репликам')

    # ---------- 4. НУЛЬ C: перестановка меток ----------
    names = list(rows)
    obs = np.array([rows[n]['osi'] for n in names])
    ur = obs[names.index('urantia')]
    stat_obs = float(np.min(np.delete(obs, names.index('urantia'))) - ur)  # насколько Урантия ниже ближайшего
    rng3 = np.random.default_rng(SEED)
    hits = 0
    for _ in range(PERM_C):
        perm = rng3.permutation(obs)
        s = float(np.min(np.delete(perm, names.index('urantia'))) - perm[names.index('urantia')])
        if s >= stat_obs:
            hits += 1
    p_c = (hits + 1) / (PERM_C + 1)
    log(f'нуль C: наблюдаемая статистика {stat_obs:+.4f}, p = {p_c:.5f}')

    # ---------- 5. Попарные сравнения + Holm ----------
    pairs = []
    for n in names:
        if n == 'urantia':
            continue
        a = np.array(rows['urantia']['windows'])
        b = np.array(rows[n]['windows'])
        d_obs = float(np.mean(b) - np.mean(a))          # >0 значит Урантия ниже (лучше)
        pooled = np.concatenate([a, b])
        rng4 = np.random.default_rng(SEED + 7)
        hits = 0
        for _ in range(2000):
            perm = rng4.permutation(pooled)
            da = perm[:a.size].mean()
            db = perm[a.size:].mean()
            if (db - da) >= d_obs:
                hits += 1
        pairs.append({'other': n, 'delta': d_obs, 'p': (hits + 1) / 2001})
    pairs.sort(key=lambda x: x['p'])
    m = len(pairs)
    for i, pr in enumerate(pairs):
        pr['holm_threshold'] = 0.05 / (m - i)
        pr['holm_significant'] = pr['p'] <= pr['holm_threshold'] and all(
            q['p'] <= 0.05 / (m - j) for j, q in enumerate(pairs[:i + 1]))

    ur_ci = rows['urantia']['ci']
    best_other = min((rows[n]['osi'], n) for n in names if n != 'urantia')
    sesoi_ok = ur_ci[1] < (best_other[0] - SESOI)
    claim = bool(sesoi_ok and p_c < 0.01 and all(pr['holm_significant'] for pr in pairs))

    final = {'metric': 'OSI', 'prereg': 'urantia-osi-prereg-20261112-v2.2 sha256 8829068a5a67832355f19ffca621890450b7dad94be9aa06629e95999244163f',
             'git': '8bf33f9', 'gate': res_gate, 'corpora': rows, 'null_C_p': p_c,
             'pairs': pairs, 'sesoi': SESOI, 'sesoi_ok': sesoi_ok,
             'best_other': {'name': best_other[1], 'osi': best_other[0]},
             'claim_allowed': claim, 'elapsed_s': round(time.time() - t0, 1)}
    json.dump(final, open(OUT / 'final.json', 'w'), ensure_ascii=False, indent=1)
    log('ИТОГ: claim_allowed =', claim, '| сек', final['elapsed_s'])
    for n in names:
        log(f"  {n:<12} OSI {rows[n]['osi']:+.4f} CI {rows[n]['ci']}  нульA {rows[n]['null_A_mean']:+.4f}  TTR {rows[n]['ttr100k']:.4f}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
