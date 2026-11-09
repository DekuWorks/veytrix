import type { Tile } from "./floor";

function key(tile: Tile): string {
  return `${tile.x},${tile.y}`;
}

function heuristic(from: Tile, to: Tile): number {
  return Math.abs(from.x - to.x) + Math.abs(from.y - to.y);
}

function reconstruct(came: Map<string, string>, goal: Tile): Tile[] {
  const path: Tile[] = [goal];
  let cursor = key(goal);
  while (came.has(cursor)) {
    cursor = came.get(cursor) ?? cursor;
    const [x, y] = cursor.split(",").map(Number);
    path.push({ x, y });
  }
  path.reverse();
  return path;
}

export function findPath(
  start: Tile,
  goal: Tile,
  walkable: (x: number, y: number) => boolean,
): Tile[] {
  if (!walkable(start.x, start.y) || !walkable(goal.x, goal.y)) {
    return [];
  }
  if (start.x === goal.x && start.y === goal.y) {
    return [start];
  }
  const open: Tile[] = [start];
  const came = new Map<string, string>();
  const score = new Map<string, number>([[key(start), 0]]);
  const rank = new Map<string, number>([[key(start), heuristic(start, goal)]]);
  const closed = new Set<string>();

  while (open.length > 0) {
    open.sort((left, right) => (rank.get(key(left)) ?? 0) - (rank.get(key(right)) ?? 0));
    const current = open.shift();
    if (!current) {
      break;
    }
    if (current.x === goal.x && current.y === goal.y) {
      return reconstruct(came, current);
    }
    const currentKey = key(current);
    closed.add(currentKey);
    const steps: Tile[] = [
      { x: current.x + 1, y: current.y },
      { x: current.x - 1, y: current.y },
      { x: current.x, y: current.y + 1 },
      { x: current.x, y: current.y - 1 },
    ];
    for (const next of steps) {
      const nextKey = key(next);
      if (closed.has(nextKey) || !walkable(next.x, next.y)) {
        continue;
      }
      const nextScore = (score.get(currentKey) ?? 0) + 1;
      if (nextScore >= (score.get(nextKey) ?? Number.POSITIVE_INFINITY)) {
        continue;
      }
      came.set(nextKey, currentKey);
      score.set(nextKey, nextScore);
      rank.set(nextKey, nextScore + heuristic(next, goal));
      if (!open.some((tile) => tile.x === next.x && tile.y === next.y)) {
        open.push(next);
      }
    }
  }
  return [];
}
