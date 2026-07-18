"""cache_bus — 跨層快取失效訊號（5eu／架構健檢 W2）。

問題：web 層的回應快取需要在「資料源狀態改變」時失效，但狀態改變有兩種
入口——HTTP 端點（user-dict／經文管理，middleware 自己看得到）與**直接
呼叫 reset_*_singleton()**（測試 monkeypatch 字型路徑後重載）。sources
層不該 import web 層（分層鐵則），所以立這個零依賴的中立小模組：

- sources 的 reset 函式呼叫 :func:`bump`；
- web 的回應快取把 :func:`epoch` 納入快取 key——epoch 一變、舊條目
  自然 miss（由 LRU 淘汰，不需主動清）。

刻意極簡：一個行程內單調遞增的整數，無鎖（GIL 下 += 1 對此用途足夠；
就算極端競態丟失一次遞增，代價只是多一次快取失效或多活一輪，無正確性
問題）。
"""
from __future__ import annotations

_epoch: int = 0


def epoch() -> int:
    """目前資料世代（納入快取 key 用）。"""
    return _epoch


def bump() -> None:
    """宣告「資料源狀態已改變」——所有以 epoch 為 key 成分的快取隨之失效。"""
    global _epoch
    _epoch += 1
