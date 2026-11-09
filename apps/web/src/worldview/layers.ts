export type LayerId = "graticule" | "earthquakes" | "flights" | "vessels" | "cities" | "voice";

export type LayerSpec = {
  id: LayerId;
  label: string;
  access: "keyless" | "key" | "paid";
  canToggle: boolean;
  source: string;
  note: string;
};

/** Layer list derived from the public God's Eye catalogue. Restricted feeds stay off. */
export const LAYERS: LayerSpec[] = [
  {
    id: "graticule",
    label: "Graticule",
    access: "keyless",
    canToggle: true,
    source: "Local sample geometry",
    note: "Sample graticule. This is not a live satellite image.",
  },
  {
    id: "earthquakes",
    label: "Earthquakes",
    access: "keyless",
    canToggle: true,
    source: "U.S. Geological Survey",
    note: "Magnitude 4.5 and above, past day. Public domain. Data courtesy of the U.S. Geological Survey.",
  },
  {
    id: "flights",
    label: "Flights",
    access: "key",
    canToggle: false,
    source: "OpenSky or adsb.lol",
    note: "Needs an OpenSky or adsb.lol proxy. Data absent. Not live.",
  },
  {
    id: "vessels",
    label: "Vessels",
    access: "key",
    canToggle: false,
    source: "AISStream",
    note: "Needs an AISStream key. Data absent. Not live.",
  },
  {
    id: "cities",
    label: "Photorealistic cities",
    access: "paid",
    canToggle: false,
    source: "Cesium ion or Google Maps",
    note: "Needs a Cesium ion token or a metered Google Maps key. Not enabled.",
  },
  {
    id: "voice",
    label: "Voice",
    access: "paid",
    canToggle: false,
    source: "OpenAI",
    note: "Needs a paid model key. Not enabled.",
  },
];

export const USGS_FEED = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson";

export type Quake = {
  id: string;
  mag: number;
  place: string;
  time: number;
  lon: number;
  lat: number;
};

export function readQuakes(body: unknown): Quake[] {
  if (!body || typeof body !== "object" || !("features" in body) || !Array.isArray(body.features)) {
    return [];
  }
  const rows: Quake[] = [];
  for (const feature of body.features) {
    if (!feature || typeof feature !== "object") {
      continue;
    }
    const geometry = "geometry" in feature ? feature.geometry : null;
    const properties = "properties" in feature ? feature.properties : null;
    if (!geometry || typeof geometry !== "object" || !properties || typeof properties !== "object") {
      continue;
    }
    const coordinates = "coordinates" in geometry ? geometry.coordinates : null;
    if (!Array.isArray(coordinates) || coordinates.length < 2) {
      continue;
    }
    const lon = Number(coordinates[0]);
    const lat = Number(coordinates[1]);
    const mag = Number("mag" in properties ? properties.mag : NaN);
    const place = "place" in properties && typeof properties.place === "string" ? properties.place : "Unnamed";
    const time = Number("time" in properties ? properties.time : NaN);
    const id = "id" in feature && (typeof feature.id === "string" || typeof feature.id === "number") ? String(feature.id) : `${lon},${lat}`;
    if (!Number.isFinite(lon) || !Number.isFinite(lat) || !Number.isFinite(mag)) {
      continue;
    }
    rows.push({ id, mag, place, time: Number.isFinite(time) ? time : Date.now(), lon, lat });
  }
  return rows.slice(0, 40);
}
