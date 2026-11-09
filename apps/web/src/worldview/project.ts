/** Orthographic globe maths. Original. Not copied from Cesium. */
export function project(
  lat: number,
  lon: number,
  centreLat: number,
  centreLon: number,
  radius: number,
): { x: number; y: number } | null {
  const phi = (lat * Math.PI) / 180;
  const lambda = (lon * Math.PI) / 180;
  const phi0 = (centreLat * Math.PI) / 180;
  const lambda0 = (centreLon * Math.PI) / 180;
  const facing = Math.sin(phi0) * Math.sin(phi) + Math.cos(phi0) * Math.cos(phi) * Math.cos(lambda - lambda0);
  if (facing < 0) {
    return null;
  }
  return {
    x: radius * Math.cos(phi) * Math.sin(lambda - lambda0),
    y: radius * (Math.cos(phi0) * Math.sin(phi) - Math.sin(phi0) * Math.cos(phi) * Math.cos(lambda - lambda0)),
  };
}
