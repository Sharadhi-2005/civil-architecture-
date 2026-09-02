"""
Genetic Algorithm (GA) — the multi-objective floor plan optimizer.

A pure CSP solver (src/csp_solver.py) only proves a layout is *valid*; it
has no notion of one valid layout being *better* than another. The GA
searches over layouts to optimize several competing objectives at once:
  - space utilization  (how close each room's actual area is to target)
  - ventilation         (do exterior-facing rooms actually touch a wall)
  - adjacency           (do required room connections actually share a wall)
  - shape quality        (penalize thin sliver rooms)

Genome: a permutation of room names, decoded into geometry via
BSPTree(plot, rooms, genome).render() — see src/bsp_partition.py. So the
GA is really searching "what order should rooms be sliced in" to get the
best trade-off across all four objectives simultaneously.
"""

import random
from typing import Dict, List, Optional
from .models import Plot, Room, Rect
from .graph_model import AdjacencyGraph
from .bsp_partition import BSPTree

DEFAULT_WEIGHTS = {"utilization": 1.0, "ventilation": 1.0, "adjacency": 2.0, "shape": 0.5}


class FloorPlanGA:
    def __init__(self, plot: Plot, rooms: List[Room], graph: AdjacencyGraph,
                 population_size: int = 40, generations: int = 60,
                 mutation_rate: float = 0.2, elite_count: int = 4,
                 weights: Optional[Dict[str, float]] = None, seed: Optional[int] = None):
        self.plot = plot
        self.rooms = rooms
        self.room_names = [r.name for r in rooms]
        self.graph = graph
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.elite_count = elite_count
        self.weights = weights or DEFAULT_WEIGHTS
        self.rng = random.Random(seed)
        self.history: List[float] = []
        self.best_genome: Optional[List[str]] = None
        self.best_fitness: float = -1.0

    # ---------- genome <-> layout ----------

    def decode(self, genome: List[str]) -> Dict[str, Rect]:
        return BSPTree(self.plot, self.rooms, genome).render()

    # ---------- fitness ----------

    def fitness(self, genome: List[str]) -> float:
        return self.score_assignment(self.decode(genome))

    def score_assignment(self, assignment: Dict[str, Rect]) -> float:
        rooms_by_name = {r.name: r for r in self.rooms}

        # 1. space utilization: how close each room's actual area is to its target
        util_terms = []
        for name, rect in assignment.items():
            room = rooms_by_name[name]
            target = (room.min_area + room.max_area) / 2
            deviation = abs(rect.area - target) / target if target else 0
            util_terms.append(max(0.0, 1.0 - deviation))
        utilization = sum(util_terms) / len(util_terms) if util_terms else 0.0

        # 2. ventilation: fraction of exterior-required rooms actually on the boundary
        ext_rooms = [r for r in self.rooms if r.needs_exterior_wall]
        if ext_rooms:
            on_boundary = 0
            for r in ext_rooms:
                rect = assignment[r.name]
                if rect.x == 0 or rect.y == 0 or rect.x2 == self.plot.width or rect.y2 == self.plot.height:
                    on_boundary += 1
            ventilation = on_boundary / len(ext_rooms)
        else:
            ventilation = 1.0

        # 3. adjacency satisfaction, from the bubble-diagram graph
        adjacency = self.graph.adjacency_score(assignment)

        # 4. shape quality: penalize sliver rooms below their declared min_dim
        shape_terms = []
        for name, rect in assignment.items():
            room = rooms_by_name[name]
            worst_dim = min(rect.w, rect.h)
            shape_terms.append(1.0 if worst_dim >= room.min_dim else worst_dim / max(room.min_dim, 1))
        shape = sum(shape_terms) / len(shape_terms) if shape_terms else 0.0

        w = self.weights
        total_w = sum(w.values())
        return (w["utilization"] * utilization + w["ventilation"] * ventilation +
                w["adjacency"] * adjacency + w["shape"] * shape) / total_w

    # ---------- GA operators ----------

    def _random_genome(self) -> List[str]:
        g = list(self.room_names)
        self.rng.shuffle(g)
        return g

    def _tournament_select(self, population: List[List[str]], fitnesses: List[float], k: int = 3) -> List[str]:
        contestants = self.rng.sample(range(len(population)), min(k, len(population)))
        best = max(contestants, key=lambda i: fitnesses[i])
        return population[best]

    def _order_crossover(self, parent_a: List[str], parent_b: List[str]) -> List[str]:
        """Order Crossover (OX) — the standard crossover for permutation
        genomes; ensures the child is always a valid permutation (no room
        duplicated or missing), unlike naive single-point crossover."""
        n = len(parent_a)
        i, j = sorted(self.rng.sample(range(n), 2))
        child: List[Optional[str]] = [None] * n
        child[i:j] = parent_a[i:j]
        fill = [g for g in parent_b if g not in child[i:j]]
        pos = 0
        for k in range(n):
            if child[k] is None:
                child[k] = fill[pos]
                pos += 1
        return child  # type: ignore

    def _mutate(self, genome: List[str]) -> List[str]:
        genome = list(genome)
        if self.rng.random() < self.mutation_rate and len(genome) >= 2:
            i, j = self.rng.sample(range(len(genome)), 2)
            genome[i], genome[j] = genome[j], genome[i]
        return genome

    # ---------- main loop ----------

    def run(self) -> Dict[str, Rect]:
        population = [self._random_genome() for _ in range(self.population_size)]

        for _gen in range(self.generations):
            fitnesses = [self.fitness(g) for g in population]
            gen_best_idx = max(range(len(population)), key=lambda i: fitnesses[i])
            if fitnesses[gen_best_idx] > self.best_fitness:
                self.best_fitness = fitnesses[gen_best_idx]
                self.best_genome = population[gen_best_idx]
            self.history.append(self.best_fitness)

            ranked = sorted(range(len(population)), key=lambda i: fitnesses[i], reverse=True)
            next_population = [population[i] for i in ranked[:self.elite_count]]  # elitism

            while len(next_population) < self.population_size:
                parent_a = self._tournament_select(population, fitnesses)
                parent_b = self._tournament_select(population, fitnesses)
                child = self._order_crossover(parent_a, parent_b)
                child = self._mutate(child)
                next_population.append(child)

            population = next_population

        return self.decode(self.best_genome)
