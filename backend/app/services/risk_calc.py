"""Авторозрахунок залишкового ризику з ефективності контролів (ТЗ §8).

Ефективність контролю виводиться зі статусу його впровадження в контексті ІКС.
Залишкова ймовірність = притаманна, зменшена на середню ефективність пов'язаних
контролів (підлога 1). Вплив (impact) контролі не зменшують — він визначається
активом. Розрахунок не зберігається автоматично: ендпойнт дає прев'ю; застосування —
явне (human-in-the-loop), із записом в історію RiskAssessment.
"""

import math

from app.models import effective_status_for_system

# Статус впровадження → ефективність [0..1]; not_applicable пропускається (None)
_STATUS_EFFECTIVENESS = {
    "implemented": 1.0,
    "partial": 0.5,
    "not_implemented": 0.0,
}


def control_effectiveness(control, system_id: int | None) -> float | None:
    """Ефективність одного контролю в контексті ІКС; None = поза областю (NA)."""
    status = effective_status_for_system(control.implementations, system_id)
    if status is None:  # немає впровадження
        return 0.0
    if status == "not_applicable":
        return None  # не враховуємо у середньому
    return _STATUS_EFFECTIVENESS.get(status, 0.0)


def aggregate_effectiveness(controls, system_id: int | None) -> float:
    effs = [e for c in controls if (e := control_effectiveness(c, system_id)) is not None]
    if not effs:
        return 0.0
    return sum(effs) / len(effs)


def effectiveness_for_risk(risk) -> tuple[float, int | None]:
    """Сукупна ефективність для ризику. Кілька ІКС → консервативно найгірша
    (мінімальна ефективність). Без ІКС — загальноорганізаційний контекст."""
    controls = list(risk.controls)
    if not controls:
        return 0.0, None
    systems = list(risk.systems)
    if not systems:
        return aggregate_effectiveness(controls, None), None
    scored = [(aggregate_effectiveness(controls, s.id), s.id) for s in systems]
    return min(scored, key=lambda pair: pair[0])


def compute_residual(
    inherent_likelihood: int | None, inherent_impact: int | None, effectiveness: float
) -> tuple[int | None, int | None]:
    """Залишкові (ймовірність, вплив). Ймовірність зменшується ефективністю
    контролів (підлога 1, стеля 5); вплив не змінюється."""
    if inherent_likelihood is None or inherent_impact is None:
        return None, None
    residual_likelihood = math.ceil(inherent_likelihood * (1 - effectiveness))
    residual_likelihood = max(1, min(residual_likelihood, 5))
    return residual_likelihood, inherent_impact
