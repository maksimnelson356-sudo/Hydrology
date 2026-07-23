"""
core/profile.py
Морфопрофиль с РЕАЛЬНЫМ разделением на отсеки (русловый + левая/правая пойма)
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import IntEnum
import math


class PointCode(IntEnum):
    NORMAL = 0
    WATER_EDGE = 1
    POYMA_BOUNDARY = 2
    THALWEG = 3


@dataclass
class ProfilePoint:
    b: float
    h: float
    code: PointCode = PointCode.NORMAL
    n: Optional[float] = None
    alpha_deg: Optional[float] = None


@dataclass
class MorphoProfile:
    name: str = "Профиль 1"
    points: List[ProfilePoint] = field(default_factory=list)
    thalweg_h: Optional[float] = None
    left_poyma_bound_b: Optional[float] = None
    right_poyma_bound_b: Optional[float] = None
    slope_i: float = 0.0001
    n_ruslo: float = 0.025
    n_left: float = 0.035
    n_right: float = 0.035

    def __post_init__(self):
        if self.points:
            self._normalize_b()
            self._detect_boundaries_from_codes()

    def _normalize_b(self):
        if not self.points:
            return
        min_b = min(p.b for p in self.points)
        for p in self.points:
            p.b = p.b - min_b

    def _detect_boundaries_from_codes(self):
        thalweg_points = [p for p in self.points if p.code == PointCode.THALWEG]
        if thalweg_points:
            self.thalweg_h = min(p.h for p in thalweg_points)

        poyma_bounds = [p for p in self.points if p.code == PointCode.POYMA_BOUNDARY]
        if len(poyma_bounds) >= 1:
            sorted_bounds = sorted(poyma_bounds, key=lambda p: p.b)
            self.left_poyma_bound_b = sorted_bounds[0].b
            if len(sorted_bounds) > 1:
                self.right_poyma_bound_b = sorted_bounds[-1].b

    @classmethod
    def from_excel(cls, filepath: str, sheet_name=0, 
                   col_b='B', col_h='H', col_code='Код', 
                   col_n='n', col_alpha='alpha', profile_name=None):
        df = pd.read_excel(filepath, sheet_name=sheet_name)
        points = []
        for _, row in df.iterrows():
            try:
                b = float(row[col_b])
                h = float(row[col_h])
                code_val = int(row[col_code]) if col_code in df.columns and pd.notna(row[col_code]) else 0
                code = PointCode(code_val) if code_val in [0,1,2,3] else PointCode.NORMAL
                n = float(row[col_n]) if col_n in df.columns and pd.notna(row[col_n]) else None
                alpha = float(row[col_alpha]) if col_alpha in df.columns and pd.notna(row[col_alpha]) else None
                points.append(ProfilePoint(b=b, h=h, code=code, n=n, alpha_deg=alpha))
            except:
                continue
        name = profile_name or f"Профиль из {filepath}"
        return cls(name=name, points=points)

    def get_sorted_points(self):
        return sorted(self.points, key=lambda p: p.b)

    def compute_geometry_at_h(self, h: float) -> Dict[str, float]:
        """
        Расчёт площади живого сечения (ω), ширины поверхности (B)
        и смоченного периметра (χ) при заданном уровне воды h.

        Формула площади (трапеции по глубинам):
            ω = Σ 0.5·(depth₁ + depth₂)·Δb
        где depth = h - h_профиля (глубина в точке).
        """
        pts = self.get_sorted_points()
        if not pts:
            return {'omega_total': 0.0, 'b_total': 0.0, 'chi_total': 0.0, 'h': h}

        min_h = min(p.h for p in pts)
        if h < min_h:
            return {'omega_total': 0.0, 'b_total': 0.0, 'chi_total': 0.0, 'h': h}

        omega = 0.0
        chi = 0.0
        b_left = None
        b_right = None
        # prev хранит (b, h_профиля) последней точки ниже уровня воды
        # или точку левого пересечения (b_int, h)
        prev = None

        for i, p in enumerate(pts):
            p_below = (p.h <= h)

            if p_below:
                if prev is None:
                    # Первая точка ниже воды — проверяем, была ли предыдущая выше
                    if i > 0 and pts[i - 1].h > h:
                        # Вычисляем левое пересечение водной поверхности с профилем
                        prev_p = pts[i - 1]
                        frac = (h - prev_p.h) / (p.h - prev_p.h)
                        b_int = prev_p.b + frac * (p.b - prev_p.b)
                        prev = (b_int, h)
                        b_left = b_int
                        # Не делаем continue — нужно накопить площадь для текущей точки
                    else:
                        prev = (p.b, p.h)
                        b_left = p.b
                        continue  # Первая точка — нет предыдущей для трапеции

                # Накопление площади: трапеция по глубинам
                depth_prev = h - prev[1]
                depth_curr = h - p.h
                width = p.b - prev[0]
                omega += 0.5 * (depth_prev + depth_curr) * width
                chi += np.hypot(p.b - prev[0], p.h - prev[1])
                prev = (p.b, p.h)
                b_right = p.b
            else:
                # Точка выше уровня воды
                if prev is not None and prev[1] < h:
                    # Правое пересечение водной поверхности с профилем
                    prev_b, prev_h = prev
                    frac = (h - prev_h) / (p.h - prev_h)
                    b_int = prev_b + frac * (p.b - prev_b)
                    # Треугольник от предыдущей точки до пересечения
                    depth_prev = h - prev_h
                    omega += 0.5 * depth_prev * (b_int - prev_b)
                    chi += np.hypot(b_int - prev_b, h - prev_h)
                    b_right = b_int
                    break
                # Если prev is None или prev на уровне воды — пропускаем

        if b_left is None or b_right is None:
            return {'omega_total': 0.0, 'b_total': 0.0, 'chi_total': 0.0, 'h': h}

        b_surface = b_right - b_left
        return {
            'omega_total': round(omega, 3),
            'b_total': round(b_surface, 2),
            'chi_total': round(chi, 3),
            'h': round(h, 2)
        }

    def get_geometry_by_compartments(self, h: float) -> Dict[str, Dict]:
        """
        РЕАЛЬНОЕ разделение на отсеки по границам поймы.
        Согласно СП 33-101-2003 п. 7.4 разделяем на:
        - Левую пойму
        - Русловую часть
        - Правую пойму
        """
        pts = self.get_sorted_points()
        if not pts or h <= min(p.h for p in pts):
            return {
                'total': {'omega_total': 0.0, 'b_total': 0.0, 'chi_total': 0.0, 'h': h},
                'left_poyma': {'omega': 0.0, 'b': 0.0, 'chi': 0.0},
                'ruslo': {'omega': 0.0, 'b': 0.0, 'chi': 0.0},
                'right_poyma': {'omega': 0.0, 'b': 0.0, 'chi': 0.0}
            }

        # Определяем границы отсеков
        b_min = min(p.b for p in pts)
        b_max = max(p.b for p in pts)
        left_bound = self.left_poyma_bound_b if self.left_poyma_bound_b is not None else b_min
        right_bound = self.right_poyma_bound_b if self.right_poyma_bound_b is not None else b_max

        # Расчет для каждого отсека
        left_poyma = self._compute_compartment_geometry(h, b_min, left_bound)
        ruslo = self._compute_compartment_geometry(h, left_bound, right_bound)
        right_poyma = self._compute_compartment_geometry(h, right_bound, b_max)

        # Общая геометрия
        total = self.compute_geometry_at_h(h)

        return {
            'total': total,
            'left_poyma': left_poyma,
            'ruslo': ruslo,
            'right_poyma': right_poyma
        }

    def _compute_compartment_geometry(self, h: float, b_start: float, b_end: float) -> Dict[str, float]:
        """
        Расчет геометрических характеристик для отсека между b_start и b_end.
        """
        if b_start >= b_end:
            return {'omega': 0.0, 'b': 0.0, 'chi': 0.0}

        pts = self.get_sorted_points()
        pts_in_range = [p for p in pts if b_start <= p.b <= b_end]

        if not pts_in_range:
            return {'omega': 0.0, 'b': 0.0, 'chi': 0.0}

        omega = 0.0
        chi = 0.0
        prev = None
        b_left = None
        b_right = None

        # Добавляем граничные точки при необходимости
        all_pts = sorted(pts, key=lambda p: p.b)
        working_pts = []

        for p in all_pts:
            if p.b < b_start:
                prev = p
                continue
            elif p.b > b_end:
                if prev is not None and prev.b < b_end:
                    # Интерполируем точку на правой границе
                    frac = (b_end - prev.b) / (p.b - prev.b)
                    h_interp = prev.h + frac * (p.h - prev.h)
                    working_pts.append(ProfilePoint(b=b_end, h=h_interp))
                break
            else:
                if prev is not None and prev.b < b_start:
                    # Интерполируем точку на левой границе
                    frac = (b_start - prev.b) / (p.b - prev.b)
                    h_interp = prev.h + frac * (p.h - prev.h)
                    working_pts.append(ProfilePoint(b=b_start, h=h_interp))
                working_pts.append(p)
                prev = p

        if not working_pts:
            return {'omega': 0.0, 'b': 0.0, 'chi': 0.0}

        # Расчет площади и смоченного периметра
        # prev хранит (b, h_профиля) последней точки ниже уровня воды
        # или точку левого пересечения (b_int, h)
        prev = None
        for i, p in enumerate(working_pts):
            p_below = (p.h <= h)

            if p_below:
                if prev is None:
                    # Первая точка ниже воды — проверяем, была ли предыдущая выше
                    if i > 0 and working_pts[i - 1].h > h:
                        prev_p = working_pts[i - 1]
                        frac = (h - prev_p.h) / (p.h - prev_p.h)
                        b_int = prev_p.b + frac * (p.b - prev_p.b)
                        prev = (b_int, h)
                        b_left = b_int
                    else:
                        prev = (p.b, p.h)
                        b_left = p.b if b_left is None else b_left
                        continue  # Первая точка — нет предыдущей для трапеции

                # Накопление площади: трапеция по глубинам
                depth_prev = h - prev[1]
                depth_curr = h - p.h
                width = p.b - prev[0]
                omega += 0.5 * (depth_prev + depth_curr) * width
                chi += np.hypot(p.b - prev[0], p.h - prev[1])
                prev = (p.b, p.h)
                b_right = p.b
            else:
                # Точка выше уровня воды
                if prev is not None and prev[1] < h:
                    prev_b, prev_h = prev
                    frac = (h - prev_h) / (p.h - prev_h)
                    b_int = prev_b + frac * (p.b - prev_b)
                    depth_prev = h - prev_h
                    omega += 0.5 * depth_prev * (b_int - prev_b)
                    chi += np.hypot(b_int - prev_b, h - prev_h)
                    b_right = b_int
                    break

        if b_left is not None and b_right is not None:
            b_surface = b_right - b_left
        else:
            b_surface = 0.0

        return {
            'omega': round(omega, 3),
            'b': round(b_surface, 2),
            'chi': round(chi, 3)
        }

    def get_n_at_b(self, b: float) -> float:
        pts = self.get_sorted_points()
        if not pts:
            return self.n_ruslo
        current_n = self.n_ruslo
        for p in pts:
            if p.n is not None:
                current_n = p.n
            if p.b > b:
                break
        return current_n

    def get_cos_alpha_at_b(self, b: float) -> float:
        pts = self.get_sorted_points()
        if not pts:
            return 1.0
        current_alpha = 0.0
        for p in pts:
            if p.alpha_deg is not None:
                current_alpha = p.alpha_deg
            if p.b > b:
                break
        return math.cos(math.radians(current_alpha))

    def build_curves(self, dh: float = 0.1):
        if not self.points:
            return pd.DataFrame()
        hs = np.arange(min(p.h for p in self.points),
                       max(p.h for p in self.points) + dh, dh)
        rows = []
        for hh in hs:
            geom = self.compute_geometry_at_h(hh)
            rows.append({
                'H': round(hh, 2),
                'ω_total': geom['omega_total'],
                'B_total': geom['b_total']
            })
        return pd.DataFrame(rows)