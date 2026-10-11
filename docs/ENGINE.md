# Engine: how it models the day

Times are minutes since midnight. All data is fictional and simulated.

## Planning
- **Solver:** cheapest insertion, then relocate, swap and 2-opt local search. Deterministic.
- **Objective, in order:** fewest undeliverable, fewest moved, least driving time. Return to depot is not counted.
- **Hard constraints** (never relaxed): capacity at every point, time windows, shift end, closures, frozen stops.

## Waiting and holding
A vehicle that arrives early waits at the customer and the wait is shown on the stop. If it would
wait more than 20 minutes it holds where it is instead (shown as idle time before the next leg), so it
is not stuck at a customer and stays available for rescue or replanning.

## Replanning from time T
- **Frozen:** completed stops, a stop in progress, and the next stop of a vehicle that is mid-leg.
  There are no road positions, so a vehicle cannot be redirected before it arrives.
- **Vehicle failure:** stops after the failure time are removed. A stop in progress at that moment
  counts as delivered. A leg that was committed but not reached is void.
- **Parcels stay on their vehicle** once it has left the depot. They are delivered by it or reported
  broken. Only parcels of a failed vehicle (collected at the breakdown site) and urgent parcels
  (collected at the depot) can change vehicle.
- **Pickup stops:** a rescued parcel is collected at the breakdown site (5 min handover) before it is
  delivered. Consecutive pickups at the same place share one handover.
- **Road closure:** takes effect for legs departing after it is reported; it cannot change history.
- **Urgent delivery:** collected at the depot (or a stated pickup place), so a vehicle that has left
  must come back for it.

## Kept, moved, broken
- **kept:** same vehicle, window met. A change in service time under 15 minutes is shown, not "moved".
- **moved:** different vehicle, or service time shifted by 15 minutes or more, or the visiting order
  of deliveries on that vehicle changed.
- **broken:** cannot be delivered in its window, or at all. The reason says why.
- **new:** an urgent delivery that was placed (it was not in the original plan).

## Independent validator
`detour/validator` takes plain dicts and imports nothing from the engine (a test enforces this).
Every revised plan is validated before it is returned; an invalid plan raises `PlanInvalid` and is
never shown as valid.
