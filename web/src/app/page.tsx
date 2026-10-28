"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";

const StationMap = dynamic(
  () => import("@/components/StationMap"),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[520px] items-center justify-center rounded-xl bg-slate-900 text-slate-400">
        Loading Paris map...
      </div>
    ),
  },
);

import {
  Activity,
  Bike,
  Clock3,
  Database,
  MapPin,
  RefreshCw,
  Search,
  Zap,
  BarChart3,
  TrendingDown,
  LayoutDashboard,
  ShieldCheck,
  CalendarDays,
  ChevronRight,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Line,
  LineChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Station = {
  stationcode: string;
  name: string;
  latitude: number;
  longitude: number;
  capacity: number | null;
  bikes_available: number;
  docks_available: number;
  mechanical_bikes: number | null;
  electric_bikes: number | null;
  last_observed_at: string;
};

type StationsData = {
  generated_at: string;
  station_count: number;
  stations: Station[];
};

type HourlyRecord = {
  hour_utc: string;
  station_count: number;
  observation_count: number;
  avg_bikes_available: number;
  avg_docks_available: number;
  pct_observations_without_bikes: number;
};

type HourlyData = {
  generated_at: string;
  hour_count: number;
  hours: HourlyRecord[];
};

type HealthData = {
  generated_at: string;
  freshness: {
    latest_poll_age_seconds: number;
    threshold_seconds: number;
    is_fresh: boolean;
  };
  automated_polling: {
    expected_polls: number;
    recorded_polls: number;
    missing_polls: number;
    coverage_percent: number;
  };
  storage: {
    duckdb_observations: number;
    unique_event_ids: number;
    duplicate_event_ids: number;
    parquet_files: number;
    parquet_observations: number;
    row_counts_match: boolean;
  };
};

type InsightData = {
  generated_at: string;
  history_window_days: number;
  empty_window_days: number;
  pattern_window_days: number;
  history_by_station: Record<string, [string, number, number, number, number][]>;
  empty_frequency: {
    stationcode: string;
    station_name: string;
    observation_count: number;
    empty_observations: number;
    empty_pct: number;
    first_observed_at: string;
    last_observed_at: string;
  }[];
  weekday_hour_pattern: {
    weekday_iso: number;
    hour_local: number;
    observation_count: number;
    station_count: number;
    avg_bikes_available: number;
    empty_pct: number;
  }[];
};

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatTime(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Unknown";

  return date.toLocaleString("en-GB", {
    timeZone: "Europe/Paris",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: typeof Bike;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-400">{title}</span>
        <Icon size={19} className="text-emerald-400" />
      </div>

      <div className="mt-5 text-3xl font-semibold tracking-tight text-white">
        {value}
      </div>

      <div className="mt-2 text-xs text-slate-500">{subtitle}</div>
    </div>
  );
}

export default function Home() {
  const [stationsData, setStationsData] = useState<StationsData | null>(null);
  const [hourlyData, setHourlyData] = useState<HourlyData | null>(null);
  const [healthData, setHealthData] = useState<HealthData | null>(null);
  const [insightData, setInsightData] = useState<InsightData | null>(null);
  const [historyWindow, setHistoryWindow] = useState<"24h" | "7d">("24h");
  const [mapMode, setMapMode] = useState<"live" | "empty" | "electric">("live");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [selectedStationCode, setSelectedStationCode] = useState<string | null>(null);
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    const update = () => setNow(Date.now());

    update();

    const timer = setInterval(update, 30_000);

    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const timestamp = Date.now();

        // Read one manifest to select a consistent dataset release.
        const manifestResponse = await fetch(
          `/data/manifest.json?t=${timestamp}`,
          { cache: "no-store" },
        );

        if (!manifestResponse.ok) {
          throw new Error(
            `Manifest request failed: ${manifestResponse.status}`,
          );
        }

        const manifest: {
          release_id: string;
          published_at: string;
          files: {
            stations: string;
            hourly: string;
            health: string;
            insights: string;
          };
        } = await manifestResponse.json();

        const paths = [
          manifest.files.stations,
          manifest.files.hourly,
          manifest.files.health,
          manifest.files.insights,
        ];

        if (
          paths.some(
            (path) =>
              !path.startsWith(
                `/data/releases/${manifest.release_id}/`,
              ),
          )
        ) {
          throw new Error("Invalid dashboard release manifest");
        }

        const responses = await Promise.all(
          paths.map((path) =>
            fetch(path, { cache: "no-store" }),
          ),
        );

        for (const response of responses) {
          if (!response.ok) {
            throw new Error(
              `Release data request failed: ${response.status}`,
            );
          }
        }

        const [stations, hourly, health, insights] = await Promise.all(
          responses.map((response) => response.json()),
        );

        if (!cancelled) {
          setStationsData(stations);
          setHourlyData(hourly);
          setHealthData(health);
          setInsightData(insights);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load data");
        }
      }
    }

    load();

    const timer = setInterval(load, 60_000);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const stations = useMemo(
    () => stationsData?.stations ?? [],
    [stationsData],
  );

  const totals = useMemo(
    () => ({
      bikes: stations.reduce(
        (sum, station) => sum + station.bikes_available,
        0,
      ),
      electric: stations.reduce(
        (sum, station) => sum + (station.electric_bikes ?? 0),
        0,
      ),
      docks: stations.reduce(
        (sum, station) => sum + station.docks_available,
        0,
      ),
      empty: stations.filter((station) => station.bikes_available === 0).length,
    }),
    [stations],
  );

  const latestObservation = useMemo(() => {
    const timestamps = stations
      .map((station) => new Date(station.last_observed_at).getTime())
      .filter(Number.isFinite);

    return timestamps.length ? Math.max(...timestamps) : null;
  }, [stations]);

  const freshnessSeconds =
    now !== null && latestObservation !== null
      ? (now - latestObservation) / 1000
      : null;

  const isFresh =
    freshnessSeconds !== null &&
    freshnessSeconds >= 0 &&
    freshnessSeconds < 600;

  const filteredStations = useMemo(() => {
    const term = query.toLowerCase().trim();

    return stations
      .filter(
        (station) =>
          station.name.toLowerCase().includes(term) ||
          station.stationcode.includes(term),
      )
      .sort((a, b) => b.bikes_available - a.bikes_available)
      .slice(0, 12);
  }, [stations, query]);

  const selectedStation = stations.find(s => s.stationcode === selectedStationCode);
  const selectedEmpty = insightData?.empty_frequency.find(s => s.stationcode === selectedStationCode);
  const emptyPctByStation = useMemo(() => Object.fromEntries((insightData?.empty_frequency ?? []).map(s => [s.stationcode, s.empty_pct])), [insightData]);
  const stationHistory = (selectedStationCode && insightData?.history_by_station[selectedStationCode] || [])
    .filter(row => historyWindow === "7d" || new Date(row[0]).getTime() >= (now ?? Date.now()) - 86400000)
    .map(row => ({ hour: row[0], samples: row[1], bikes: row[2], docks: row[3], emptyPct: row[4] }));
  const rankedEmpty = (insightData?.empty_frequency ?? [])
    .filter(row => row.observation_count >= 12)
    .slice(0, 10);
  const heatmap = new Map((insightData?.weekday_hour_pattern ?? []).map(row =>
    [`${row.weekday_iso}-${row.hour_local}`, row]));
  const heatmapHours = Array.from({length:24},(_,i)=>i);
  const weekdays = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];

  if (!stationsData || !hourlyData || !healthData || !insightData) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#080d16] text-white">
        <div className="text-center">
          <Bike className="mx-auto mb-4 text-emerald-400" size={36} />
          <p>{error || "Loading Vélib' observations..."}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#080d16] text-slate-200 selection:bg-cyan-400/30">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(6,182,212,0.09),transparent_50%)]" />
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-white/10 bg-[#0c1422]/95 px-4 py-7 backdrop-blur-xl lg:flex">
        <a href="#overview" className="mb-12 flex items-center gap-3 px-2">
          <div className="rounded-2xl bg-gradient-to-br from-cyan-300 to-emerald-400 p-2.5 text-slate-950"><Bike size={24}/></div>
          <div><p className="font-bold tracking-tight text-white">Vélib&apos; Pulse</p><p className="text-[10px] uppercase tracking-[0.2em] text-cyan-300">Intelligence</p></div>
        </a>
        <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-600">Workspace</p>
        {[
          {href:"#overview",label:"Overview",icon:LayoutDashboard},
          {href:"#station-map",label:"Station intelligence",icon:MapPin},
          {href:"#patterns",label:"Mobility patterns",icon:CalendarDays},
          {href:"#pipeline",label:"Pipeline health",icon:ShieldCheck},
          {href:"#explorer",label:"Station explorer",icon:Search},
        ].map(item => <a key={item.href} href={item.href} className="group mb-1 flex items-center gap-3 rounded-xl px-3 py-3 text-sm text-slate-400 transition hover:bg-cyan-400/10 hover:text-cyan-200"><item.icon size={17}/>{item.label}<ChevronRight size={13} className="ml-auto opacity-0 transition group-hover:opacity-100"/></a>)}
        <div className="mt-auto rounded-2xl border border-cyan-400/10 bg-cyan-400/[0.04] p-4 text-xs leading-6 text-slate-400"><span className="font-semibold text-cyan-300">DATA ENGINEERING</span><br/>5-minute snapshots<br/>Historical Parquet + dbt<br/>Measured pipeline health</div>
      </aside>
      <div className="relative mx-auto max-w-7xl px-5 py-8 md:px-10 lg:ml-60 lg:max-w-none lg:px-10 xl:px-14">
        <header id="overview" className="mb-10 flex scroll-mt-8 flex-wrap items-center justify-between gap-5">
          <div className="flex items-center gap-4">
            <div className="rounded-xl bg-gradient-to-br from-cyan-300 to-emerald-400 p-3 text-slate-950">
              <Bike size={26} strokeWidth={2.5} />
            </div>

            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">
                Vélib&apos; Pulse
              </h1>
              <p className="text-sm text-slate-500">
                Paris mobility intelligence
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div
              className={`rounded-full border px-4 py-2 text-xs font-semibold ${
                isFresh
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                  : "border-amber-500/30 bg-amber-500/10 text-amber-400"
              }`}
            >
              ● {isFresh ? "DATA FRESH" : "DATA STALE"}
            </div>

            <span className="flex items-center gap-2 text-xs text-slate-500">
              <Clock3 size={14} />
              Last observation:{" "}
              {latestObservation !== null
                ? formatTime(new Date(latestObservation).toISOString())
                : "Unknown"}
            </span>
          </div>
        </header>

        {error && (
          <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-300">
            Refresh failed: {error}. Showing previously loaded data.
          </div>
        )}

        <section className="mb-8">
          <div className="mb-5">
            <h2 className="text-xl font-semibold text-white">
              Network overview
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Latest recorded availability across{" "}
              {formatNumber(stations.length)} stations
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              title="Available bikes"
              value={formatNumber(totals.bikes)}
              subtitle="Across observed stations"
              icon={Bike}
            />

            <MetricCard
              title="Electric bikes"
              value={formatNumber(totals.electric)}
              subtitle="Reported electric availability"
              icon={Zap}
            />

            <MetricCard
              title="Available docks"
              value={formatNumber(totals.docks)}
              subtitle="Free parking spaces"
              icon={MapPin}
            />

            <MetricCard
              title="Stations without bikes"
              value={formatNumber(totals.empty)}
              subtitle="Zero bikes in latest observation"
              icon={Activity}
            />
          </div>
        </section>

        <section id="station-map" className="mb-8 scroll-mt-8 rounded-2xl border border-cyan-400/15 bg-white/[0.035] p-5 shadow-[0_0_80px_rgba(6,182,212,0.035)]">
          <div className="mb-5">
            <h2 className="text-lg font-semibold text-white">
              Explore Paris stations
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Select a station to view its latest recorded availability
            </p>
          </div>

          <div className="mb-4 flex flex-wrap gap-2">
            {([ ["live","Live bikes"], ["empty","Empty frequency"], ["electric","Electric bikes"] ] as const).map(([mode,label]) => <button key={mode} onClick={() => setMapMode(mode)} className={`rounded-full border px-4 py-2 text-xs font-semibold transition ${mapMode === mode ? "border-cyan-300 bg-cyan-300 text-slate-950" : "border-white/10 bg-slate-900 text-slate-400 hover:text-white"}`}>{label}</button>)}
          </div>
          <StationMap
            stations={stations}
            selectedStationCode={selectedStationCode}
            onSelectStation={setSelectedStationCode}
            mode={mapMode}
            emptyPctByStation={emptyPctByStation}
          />
          {selectedStation && <div className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-cyan-400/20 bg-cyan-400/[0.06] p-5">
            <div><p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-300">Station intelligence</p><h3 className="mt-1 text-lg font-bold text-white">{selectedStation.name}</h3><p className="text-xs text-slate-400">{selectedStation.stationcode} · last observed {formatTime(selectedStation.last_observed_at)}</p></div>
            <div className="flex flex-wrap gap-6 text-center"><div><p className="text-2xl font-bold text-emerald-300">{selectedStation.bikes_available}</p><p className="text-xs text-slate-500">Bikes</p></div><div><p className="text-2xl font-bold text-cyan-300">{selectedStation.electric_bikes ?? "—"}</p><p className="text-xs text-slate-500">Electric</p></div><div><p className="text-2xl font-bold text-white">{selectedStation.docks_available}</p><p className="text-xs text-slate-500">Docks</p></div><div><p className="text-2xl font-bold text-amber-300">{selectedEmpty ? `${selectedEmpty.empty_pct}%` : "—"}</p><p className="text-xs text-slate-500">Empty samples</p></div></div>
            <a href="#station-history" className="rounded-xl bg-cyan-300 px-4 py-2.5 text-xs font-bold text-slate-950 hover:bg-cyan-200">View history →</a>
          </div>}
        </section>

        <section id="station-history" className="mb-8 scroll-mt-8 grid gap-5 lg:grid-cols-[1.4fr_1fr]">
          <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-6">
            <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
              <div>
                <h2 className="flex items-center gap-2 text-lg font-semibold text-white"><BarChart3 size={20} className="text-emerald-400" />Station history</h2>
                <p className="mt-1 text-sm text-slate-500">{selectedStation ? `${selectedStation.name} · hourly averages from collected snapshots` : "Select a station in the explorer below to view historical availability"}</p>
              </div>
              <div className="flex gap-2">
                {(["24h","7d"] as const).map(w => <button key={w} onClick={() => setHistoryWindow(w)} className={`rounded-lg px-3 py-1.5 text-xs ${historyWindow === w ? "bg-emerald-400 text-slate-950" : "bg-slate-800 text-slate-300"}`}>{w}</button>)}
              </div>
            </div>
            {stationHistory.length ? <div className="h-64"><ResponsiveContainer width="100%" height="100%"><LineChart data={stationHistory}>
              <CartesianGrid stroke="#263244" strokeDasharray="3 3" vertical={false}/>
              <XAxis dataKey="hour" tickFormatter={(v:string) => new Date(v).toLocaleString("en-GB", {timeZone:"Europe/Paris",day:"2-digit",hour:"2-digit"})} stroke="#64748b" tick={{fontSize:10}} minTickGap={24}/>
              <YAxis stroke="#64748b" tick={{fontSize:11}} allowDecimals={false}/>
              <Tooltip labelFormatter={v=>formatTime(String(v))} contentStyle={{backgroundColor:"#111c2c",border:"1px solid #334155",borderRadius:12}}/>
              <Line type="monotone" dataKey="bikes" name="Avg bikes" stroke="#34d399" strokeWidth={2} dot={false}/>
              <Line type="monotone" dataKey="docks" name="Avg docks" stroke="#60a5fa" strokeWidth={2} dot={false}/>
            </LineChart></ResponsiveContainer></div> : <div className="flex h-64 items-center justify-center text-sm text-slate-500">{selectedStationCode ? "No observations in selected window" : "Choose a station from Station explorer"}</div>}
            <p className="mt-3 text-xs text-slate-500">Last {historyWindow === "24h" ? "24 hours" : "7 days"} · hourly sample averages, not rental counts.</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-6">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-white"><TrendingDown size={20} className="text-amber-400"/>Frequently empty stations</h2>
            <p className="mt-1 mb-5 text-xs text-slate-500">Last 7 days · percentage of samples with zero bikes · minimum 12 samples</p>
            <div className="space-y-2">{rankedEmpty.map((s,i)=><button key={s.stationcode} onClick={()=>{setSelectedStationCode(s.stationcode);document.querySelector("#station-map")?.scrollIntoView({behavior:"smooth"});}} className="flex w-full items-center justify-between gap-3 rounded-lg bg-slate-900/70 px-3 py-2 text-left hover:bg-slate-800">
              <span className="min-w-0 truncate text-xs text-slate-200">{i+1}. {s.station_name}</span><span className="shrink-0 text-right"><strong className="text-sm text-amber-400">{s.empty_pct}%</strong><span className="block text-[10px] text-slate-500">{s.observation_count} samples</span></span>
            </button>)}{rankedEmpty.length===0 && <p className="text-sm text-slate-500">Not enough observations yet.</p>}</div>
          </div>
        </section>

        <section id="patterns" className="mb-8 scroll-mt-8 rounded-2xl border border-white/10 bg-white/[0.035] p-6">
          <h2 className="text-lg font-semibold text-white">Weekday × hour availability patterns</h2>
          <p className="mt-1 mb-5 text-xs text-slate-500">Paris local time · last 28 days · color = percentage of recorded samples with zero bikes (darker = fewer empty samples)</p>
          <div className="overflow-x-auto"><table className="w-full min-w-[820px] border-separate border-spacing-1 text-center text-xs"><thead><tr><th className="p-1 text-slate-500">Day</th>{heatmapHours.map(h=><th key={h} className="p-1 text-slate-500">{String(h).padStart(2,"0")}</th>)}</tr></thead><tbody>
            {weekdays.map((day,i)=><tr key={day}><th className="p-1 text-left text-slate-400">{day}</th>{heatmapHours.map(hour=>{const row=heatmap.get(`${i+1}-${hour}`);const pct=row?.empty_pct ?? 0;return <td key={hour} title={row ? `${day} ${hour}:00 · ${pct}% empty samples · ${formatNumber(row.observation_count)} observations` : "No observations"} className="h-7 rounded" style={{backgroundColor:row ? `rgba(251, 191, 36, ${0.1+0.85*pct/100})` : "#1e293b"}}>{row ? Math.round(pct) : "–"}</td>})}</tr>)}
          </tbody></table></div>
          <p className="mt-3 text-xs text-slate-500">Cells show empty-sample percentages across observed stations. No data is displayed as “–”; short histories may not cover every weekday.</p>
        </section>

        <section id="pipeline" className="mb-8 scroll-mt-8 grid gap-5 lg:grid-cols-[1.7fr_1fr]">
          <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-6">
            <div className="mb-8">
              <h2 className="text-lg font-semibold text-white">
                Hourly bike availability
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Average available bikes per station · sampled observations
              </p>
            </div>

            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={hourlyData.hours}>
                  <defs>
                    <linearGradient id="bikeGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="5%"
                        stopColor="#34d399"
                        stopOpacity={0.3}
                      />
                      <stop
                        offset="95%"
                        stopColor="#34d399"
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>

                  <CartesianGrid
                    stroke="#263244"
                    strokeDasharray="3 3"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="hour_utc"
                    tickFormatter={(value: string) =>
                      new Date(value).toLocaleTimeString("en-GB", {
                        timeZone: "Europe/Paris",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    }
                    stroke="#64748b"
                    tick={{ fontSize: 11 }}
                  />

                  <YAxis
                    stroke="#64748b"
                    tick={{ fontSize: 11 }}
                    domain={["auto", "auto"]}
                  />

                  <Tooltip
                    labelFormatter={(value) => formatTime(String(value))}
                    contentStyle={{
                      backgroundColor: "#111c2c",
                      border: "1px solid #334155",
                      borderRadius: "12px",
                      color: "#fff",
                    }}
                  />

                  <Area
                    type="monotone"
                    dataKey="avg_bikes_available"
                    name="Avg. bikes"
                    stroke="#34d399"
                    strokeWidth={2.5}
                    fill="url(#bikeGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-6">
            <div className="mb-7 flex items-center gap-3">
              <Database size={20} className="text-emerald-400" />
              <h2 className="text-lg font-semibold text-white">
                Pipeline health
              </h2>
            </div>

            <div className="space-y-6">
              <div>
                <div className="mb-2 flex justify-between text-sm">
                  <span className="text-slate-400">Poll coverage</span>
                  <span className="font-semibold text-white">
                    {healthData.automated_polling.coverage_percent}%
                  </span>
                </div>

                <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                  <div
                    className="h-full rounded-full bg-emerald-400"
                    style={{
                      width: `${Math.min(
                        100,
                        Math.max(0, healthData.automated_polling.coverage_percent),
                      )}%`,
                    }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-xl bg-slate-900/70 p-4">
                  <p className="text-xs text-slate-500">Recorded polls</p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {formatNumber(healthData.automated_polling.recorded_polls)}
                  </p>
                </div>

                <div className="rounded-xl bg-slate-900/70 p-4">
                  <p className="text-xs text-slate-500">Missing polls</p>
                  <p className="mt-2 text-2xl font-semibold text-amber-400">
                    {formatNumber(healthData.automated_polling.missing_polls)}
                  </p>
                </div>

                <div className="rounded-xl bg-slate-900/70 p-4">
                  <p className="text-xs text-slate-500">Parquet files</p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {formatNumber(healthData.storage.parquet_files)}
                  </p>
                </div>

                <div className="rounded-xl bg-slate-900/70 p-4">
                  <p className="text-xs text-slate-500">Stored observations</p>
                  <p className="mt-2 text-2xl font-semibold text-white">
                    {formatNumber(healthData.storage.duckdb_observations)}
                  </p>
                </div>
              </div>

              <div className="rounded-xl bg-slate-900/70 p-3 text-xs text-slate-400">
                <p>Storage consistency: <span className={healthData.storage.row_counts_match ? "text-emerald-400" : "text-red-400"}>{healthData.storage.row_counts_match ? "DuckDB / Parquet counts match" : "Count mismatch"}</span></p>
                <p className="mt-1">Deduplicated store: {formatNumber(healthData.storage.unique_event_ids)} unique event IDs</p>
                <p className="mt-1 text-slate-500">Kafka duplicate rate, processing lag, and recovery duration: not yet measured.</p>
              </div>
              <p className="flex items-center gap-2 text-xs text-slate-500">
                <RefreshCw size={13} />
                Health report: {formatTime(healthData.generated_at)}
              </p>
            </div>
          </div>
        </section>

        <section id="explorer" className="scroll-mt-8 rounded-2xl border border-white/10 bg-white/[0.035] p-6">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-white">
                Station explorer
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Search stations by name or station code
              </p>
            </div>

            <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-slate-900 px-4 py-2.5">
              <Search size={17} className="text-slate-500" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search stations..."
                className="w-52 bg-transparent text-sm text-white outline-none placeholder:text-slate-600"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-white/10 text-xs uppercase tracking-wider text-slate-500">
                  <th className="pb-4 font-medium">Station</th>
                  <th className="pb-4 font-medium">Code</th>
                  <th className="pb-4 text-right font-medium">Bikes</th>
                  <th className="pb-4 text-right font-medium">E-bikes</th>
                  <th className="pb-4 text-right font-medium">Docks</th>
                </tr>
              </thead>

              <tbody>
                {filteredStations.map((station) => (
                  <tr
                    key={station.stationcode}
                    onClick={() => {
                      setSelectedStationCode(station.stationcode);
                      document
                        .querySelector("#station-history")
                        ?.scrollIntoView({ behavior: "smooth" });
                    }}
                    className="cursor-pointer border-b border-white/5 hover:bg-white/5"
                  >
                    <td className="py-4 font-medium text-slate-200">
                      {station.name}
                    </td>
                    <td className="py-4 text-slate-500">
                      {station.stationcode}
                    </td>
                    <td className="py-4 text-right text-emerald-400">
                      {station.bikes_available}
                    </td>
                    <td className="py-4 text-right">
                      {station.electric_bikes ?? "—"}
                    </td>
                    <td className="py-4 text-right">
                      {station.docks_available}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {filteredStations.length === 0 && (
              <p className="py-10 text-center text-sm text-slate-500">
                No matching stations found.
              </p>
            )}
          </div>
        </section>

        <footer className="mt-8 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-600">
          <span>Vélib&apos; Pulse · Paris mobility data pipeline</span>
          <span>
            Snapshot exported: {formatTime(stationsData.generated_at)}
          </span>
        </footer>
      </div>
    </main>
  );
}
