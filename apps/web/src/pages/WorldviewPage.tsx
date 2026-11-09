import { useEffect, useRef, useState } from "react";
import { LAYERS, USGS_FEED, readQuakes, type LayerId, type Quake } from "../worldview/layers";
import { project } from "../worldview/project";

type ResearchLine = {
  id: string;
  message: string;
};

const START = new Set<LayerId>(["graticule", "earthquakes"]);

function drawGlobe(
  canvas: HTMLCanvasElement,
  centreLat: number,
  centreLon: number,
  zoom: number,
  graticule: boolean,
  quakes: Quake[],
  trackedId: string | null,
) {
  const context = canvas.getContext("2d");
  if (!context) {
    return;
  }
  const width = canvas.width;
  const height = canvas.height;
  const radius = Math.min(width, height) * 0.38 * zoom;
  const cx = width / 2;
  const cy = height / 2;
  context.clearRect(0, 0, width, height);
  context.fillStyle = "#070c0a";
  context.fillRect(0, 0, width, height);
  context.beginPath();
  context.arc(cx, cy, radius, 0, Math.PI * 2);
  context.fillStyle = "#10241c";
  context.fill();
  context.strokeStyle = "#3dff9a";
  context.lineWidth = 2;
  context.stroke();
  if (graticule) {
    context.strokeStyle = "rgba(142, 224, 184, 0.35)";
    context.lineWidth = 1;
    for (const lat of [-60, -30, 0, 30, 60]) {
      context.beginPath();
      let started = false;
      for (let lon = -180; lon <= 180; lon += 6) {
        const point = project(lat, lon, centreLat, centreLon, radius);
        if (!point) {
          started = false;
          continue;
        }
        const x = cx + point.x;
        const y = cy - point.y;
        if (!started) {
          context.moveTo(x, y);
          started = true;
        } else {
          context.lineTo(x, y);
        }
      }
      context.stroke();
    }
  }
  for (const quake of quakes) {
    const point = project(quake.lat, quake.lon, centreLat, centreLon, radius);
    if (!point) {
      continue;
    }
    context.beginPath();
    context.arc(cx + point.x, cy - point.y, quake.id === trackedId ? 6 : 3.5, 0, Math.PI * 2);
    context.fillStyle = quake.id === trackedId ? "#f4fff8" : "#8ee0b8";
    context.fill();
  }
}

export function WorldviewPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [layers, setLayers] = useState<Set<LayerId>>(START);
  const [centre, setCentre] = useState({ lat: 20, lon: 0 });
  const [zoom, setZoom] = useState(1);
  const [quakes, setQuakes] = useState<Quake[]>([]);
  const [quakeState, setQuakeState] = useState<"loading" | "public" | "absent">("loading");
  const [retrieved, setRetrieved] = useState<string>("");
  const [selected, setSelected] = useState<string | null>(null);
  const [track, setTrack] = useState(false);
  const [research, setResearch] = useState<ResearchLine[]>([]);

  useEffect(() => {
    document.title = "Worldview · Veytrix";
    const controller = new AbortController();
    void fetch(USGS_FEED, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(String(response.status));
        }
        return response.json() as Promise<unknown>;
      })
      .then((body) => {
        const rows = readQuakes(body);
        setQuakes(rows);
        setQuakeState(rows.length > 0 ? "public" : "absent");
        setRetrieved(new Date().toISOString());
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setQuakeState("absent");
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const tracked = track ? selected : null;
    const focus = quakes.find((quake) => quake.id === tracked);
    const lat = focus ? focus.lat : centre.lat;
    const lon = focus ? focus.lon : centre.lon;
    drawGlobe(canvas, lat, lon, zoom, layers.has("graticule"), layers.has("earthquakes") ? quakes : [], tracked);
  }, [centre, layers, quakes, selected, track, zoom]);

  function toggle(id: LayerId) {
    const spec = LAYERS.find((layer) => layer.id === id);
    if (!spec?.canToggle) {
      return;
    }
    setLayers((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function noteResearch() {
    const quake = quakes.find((item) => item.id === selected);
    const subject = quake ? `M ${quake.mag.toFixed(1)} ${quake.place}` : "No earthquake selected";
    const when = retrieved || "time absent";
    const message = `Astra · RESEARCH-01: Geographic research. ${subject}. Source: U.S. Geological Survey. Time: ${when}. Roads · SUPERVISOR-01 may read this. Not a broker fill. Not stored. No order is sent.`;
    setResearch((current) => [{ id: `${Date.now()}`, message }, ...current].slice(0, 5));
  }

  const freshness =
    quakeState === "loading"
      ? "USGS feed loading."
      : quakeState === "public"
        ? `Public USGS feed. Retrieved ${retrieved}. Not stored.`
        : "USGS feed absent. Not live.";

  return (
    <div className="vx-page">
      <header>
        <p className="vx-kicker">Local research</p>
        <h1 className="vx-title">Worldview</h1>
        <p className="vx-lede">
          A local research globe for Astra (RESEARCH-01) and Roads (SUPERVISOR-01). This page is local-only and not
          authenticated, like the rest of Veytrix. Notes are not stored. No order is sent.
        </p>
      </header>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section className="vx-card">
          <canvas ref={canvasRef} width={720} height={480} aria-label="Research globe" className="h-auto w-full" />
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className="vx-btn" onClick={() => setCentre((c) => ({ ...c, lon: c.lon - 15 }))}>
              Pan west
            </button>
            <button type="button" className="vx-btn" onClick={() => setCentre((c) => ({ ...c, lon: c.lon + 15 }))}>
              Pan east
            </button>
            <button type="button" className="vx-btn" onClick={() => setCentre((c) => ({ ...c, lat: Math.min(70, c.lat + 10) }))}>
              Pan north
            </button>
            <button type="button" className="vx-btn" onClick={() => setCentre((c) => ({ ...c, lat: Math.max(-70, c.lat - 10) }))}>
              Pan south
            </button>
            <button type="button" className="vx-btn" onClick={() => setZoom((value) => Math.min(2.2, value + 0.2))}>
              Zoom in
            </button>
            <button type="button" className="vx-btn" onClick={() => setZoom((value) => Math.max(0.6, value - 0.2))}>
              Zoom out
            </button>
            <button type="button" className="vx-btn" aria-pressed={track} onClick={() => setTrack((value) => !value)}>
              Track selection
            </button>
          </div>
        </section>
        <aside className="flex flex-col gap-3">
          <section className="vx-card">
            <h2 className="vx-section-title">Layers</h2>
            <ul className="mt-3 space-y-2">
              {LAYERS.map((layer) => (
                <li key={layer.id}>
                  <button
                    type="button"
                    className="vx-btn w-full text-left"
                    aria-pressed={layers.has(layer.id)}
                    disabled={!layer.canToggle}
                    onClick={() => toggle(layer.id)}
                  >
                    {layer.label}
                  </button>
                  <p className="vx-copy">
                    {layer.source}. {layer.note}
                  </p>
                </li>
              ))}
            </ul>
          </section>
          <section className="vx-card">
            <h2 className="vx-section-title">Freshness</h2>
            <p className="vx-copy">{freshness}</p>
            <p className="vx-copy">Data courtesy of the U.S. Geological Survey.</p>
          </section>
        </aside>
      </div>
      <section className="vx-card">
        <h2 className="vx-section-title">Earthquakes</h2>
        {quakes.length === 0 ? (
          <p className="vx-copy">No earthquake rows. The feed is absent or still loading. Not live until a row appears.</p>
        ) : (
          <ul className="mt-2 max-h-48 space-y-1 overflow-auto">
            {quakes.map((quake) => (
              <li key={quake.id}>
                <button
                  type="button"
                  className="vx-btn w-full text-left"
                  aria-pressed={selected === quake.id}
                  onClick={() => setSelected(quake.id)}
                >
                  M {quake.mag.toFixed(1)} {quake.place}
                </button>
              </li>
            ))}
          </ul>
        )}
        <button type="button" className="vx-btn mt-3" onClick={noteResearch}>
          Add research note
        </button>
      </section>
      <section className="vx-card">
        <h2 className="vx-section-title">Research activity</h2>
        {research.length === 0 ? (
          <p className="vx-copy">No research note yet. Not stored. No order is sent.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {research.map((line) => (
              <li key={line.id} className="text-sm text-ink">
                {line.message}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
