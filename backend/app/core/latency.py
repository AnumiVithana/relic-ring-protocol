"""
Latency Engine — computes the four physical delay components for a single hop.

For a packet travelling from Planet A → Planet B:

  1. T_fiber   : Arc travel along Planet A's equatorial fiber ring
                 from the internal entry tower to the sending tower.
                 time = arc_length / (fiber_fraction × c)

  2. T_atm_src : Signal piercing Planet A's ionized atmosphere outward.
                 time = h_A / (c / n_A)

  3. T_void    : Laser crossing the vacuum between planets.
                 time = L / c
                 where L = center_dist − (R_A + h_A) − (R_B + h_B)

  4. T_atm_dst : Signal piercing Planet B's atmosphere inward.
                 time = h_B / (c / n_B)

  5. T_towers  : Fixed 7 ms penalty per tower hit.
                 Counted once even if the same tower sends and receives.

Total latency = T_fiber + T_atm_src + T_void + T_atm_dst + T_towers
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Planet, Tower
    from .constants import UniverseConstants


# ──────────────────────────────────────────────────────────────────────────────
# Result container
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class HopLatency:
    """
    Full latency breakdown for one planet-to-planet hop.
    All times are in seconds; helper properties convert to ms.
    """
    t_fiber_s: float        # subsurface fiber arc transit
    t_atm_src_s: float      # atmosphere exit at source planet
    t_void_s: float         # vacuum laser transmission
    t_atm_dst_s: float      # atmosphere entry at destination planet
    t_towers_s: float       # tower processing penalties
    towers_hit: int         # number of distinct towers hit this hop
    void_distance_km: float # L in km (for logging / Lmax check)
    fiber_arc_km: float     # arc length traveled on fiber ring

    # ── derived ──────────────────────────────────────────────────────────────
    @property
    def total_s(self) -> float:
        return (
            self.t_fiber_s
            + self.t_atm_src_s
            + self.t_void_s
            + self.t_atm_dst_s
            + self.t_towers_s
        )

    @property
    def total_ms(self) -> float:
        return self.total_s * 1000

    # ── ms helpers ───────────────────────────────────────────────────────────
    @property
    def t_fiber_ms(self) -> float:   return self.t_fiber_s   * 1000
    @property
    def t_atm_src_ms(self) -> float: return self.t_atm_src_s * 1000
    @property
    def t_void_ms(self) -> float:    return self.t_void_s    * 1000
    @property
    def t_atm_dst_ms(self) -> float: return self.t_atm_dst_s * 1000
    @property
    def t_towers_ms(self) -> float:  return self.t_towers_s  * 1000

    # ── display ──────────────────────────────────────────────────────────────
    def breakdown(self) -> dict:
        return {
            "fiber_ms":       round(self.t_fiber_ms,   4),
            "atm_src_ms":     round(self.t_atm_src_ms, 4),
            "void_ms":        round(self.t_void_ms,    4),
            "atm_dst_ms":     round(self.t_atm_dst_ms, 4),
            "towers_ms":      round(self.t_towers_ms,  4),
            "total_ms":       round(self.total_ms,     4),
            "towers_hit":     self.towers_hit,
            "void_dist_km":   round(self.void_distance_km, 2),
            "fiber_arc_km":   round(self.fiber_arc_km, 2),
        }

    def __str__(self) -> str:
        b = self.breakdown()
        return (
            f"  fiber      : {b['fiber_ms']:>10.4f} ms  ({b['fiber_arc_km']} km arc)\n"
            f"  atm (src)  : {b['atm_src_ms']:>10.4f} ms\n"
            f"  void       : {b['void_ms']:>10.4f} ms  ({b['void_dist_km']} km)\n"
            f"  atm (dst)  : {b['atm_dst_ms']:>10.4f} ms\n"
            f"  towers ×{b['towers_hit']}  : {b['towers_ms']:>10.4f} ms\n"
            f"  ─────────────────────────────\n"
            f"  TOTAL      : {b['total_ms']:>10.4f} ms"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────────────────────────────────────

class LatencyEngine:
    """
    Stateless calculator. Inject UniverseConstants once, call compute() freely.
    """

    def __init__(self, constants: UniverseConstants):
        self.c = constants

    # ── public API ────────────────────────────────────────────────────────────

    def compute(
        self,
        src: Planet,
        dst: Planet,
        entry_tower: Tower,     # tower inside src where the packet arrives / originates
        send_tower: Tower,      # tower on src that fires the laser into void
        recv_tower: Tower,      # tower on dst that catches the laser
    ) -> HopLatency:
        """
        Compute full latency for one hop: src → dst.

        entry_tower  — where on src the packet starts its fiber journey
                       (for the origin planet this is the same as send_tower
                        if the packet starts there, but for relay planets it
                        is the tower that received the previous hop's laser)
        send_tower   — the src tower with best line-of-sight to dst
        recv_tower   — the dst tower with best line-of-sight to src
        """
        # 1. Fiber arc on the source planet
        arc_km    = src.arc_length_between_towers(entry_tower, send_tower)
        t_fiber   = arc_km / self.c.fiber_speed_km_s

        # 2. Atmosphere at source (exit)
        t_atm_src = self._atm_transit(src.atmosphere_thickness_km, src.refraction_index)

        # 3. Void distance and transit
        L         = self._void_distance(src, dst)
        t_void    = L / self.c.speed_of_light_km_s

        # 4. Atmosphere at destination (entry)
        t_atm_dst = self._atm_transit(dst.atmosphere_thickness_km, dst.refraction_index)

        # 5. Tower processing delays
        #    Count distinct towers hit: entry + send on src, recv on dst.
        #    If entry == send (same tower), count it once.
        towers_hit = self._count_towers(entry_tower, send_tower, recv_tower)
        t_towers   = towers_hit * self.c.tower_delay_s

        return HopLatency(
            t_fiber_s=t_fiber,
            t_atm_src_s=t_atm_src,
            t_void_s=t_void,
            t_atm_dst_s=t_atm_dst,
            t_towers_s=t_towers,
            towers_hit=towers_hit,
            void_distance_km=L,
            fiber_arc_km=arc_km,
        )

    def void_distance(self, src: Planet, dst: Planet) -> float:
        """Public wrapper — void distance in km between two planets."""
        return self._void_distance(src, dst)

    def exceeds_lmax(self, src: Planet, dst: Planet) -> bool:
        return self._void_distance(src, dst) > self.c.lmax_km

    # ── private helpers ───────────────────────────────────────────────────────

    def _void_distance(self, src: Planet, dst: Planet) -> float:
        """
        L = center_to_center_km − (R_src + h_src) − (R_dst + h_dst)
        x_km / y_km are already in km (scaled during config load).
        """
        center_dist = math.hypot(
            dst.x_km - src.x_km,
            dst.y_km - src.y_km,
        )
        L = center_dist - src.outer_radius_km - dst.outer_radius_km
        return max(L, 0.0)

    def _atm_transit(self, thickness_km: float, refraction_index: float) -> float:
        """
        T_atm = h / (c / n)  =  h × n / c
        Signal slows to c/n inside the ionized atmosphere shell.
        """
        speed_in_atm = self.c.speed_of_light_km_s / refraction_index
        return thickness_km / speed_in_atm

    @staticmethod
    def _count_towers(entry: Tower, send: Tower, recv: Tower) -> int:
        """
        Count distinct tower hits on this hop.
        On the source planet: entry tower + send tower (1 if they're the same).
        On the dest planet:   recv tower always counts.
        """
        src_towers = {entry.index} | {send.index}   # set deduplicates same tower
        # recv is always on a different planet so always a new tower
        return len(src_towers) + 1
