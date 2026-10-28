"use client";

import { useEffect, useMemo } from "react";
import {
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

export type MapStation = {
  stationcode: string;
  name: string;
  latitude: number;
  longitude: number;
  bikes_available: number;
  docks_available: number;
  electric_bikes: number | null;
  last_observed_at: string;
};

type Props = {
  stations: MapStation[];
  selectedStationCode?: string | null;
  onSelectStation?: (code: string) => void;
  mode?: "live" | "empty" | "electric";
  emptyPctByStation?: Record<string, number>;
};

const PARIS_CENTER: [number, number] = [48.8566, 2.3522];

function markerColor(bikes: number): string {
  if (bikes === 0) return "#f87171";
  if (bikes <= 3) return "#fbbf24";
  return "#34d399";
}

function MapFocus({
  station,
}: {
  station: MapStation | undefined;
}) {
  const map = useMap();

  useEffect(() => {
    if (!station) return;

    map.flyTo([station.latitude, station.longitude], 16, {
      duration: 1.2,
    });
  }, [map, station]);

  return null;
}

export default function StationMap({
  stations,
  selectedStationCode,
  onSelectStation,
  mode = "live",
  emptyPctByStation = {},
}: Props) {
  const validStations = useMemo(
    () =>
      stations.filter(
        (station) =>
          Number.isFinite(station.latitude) &&
          Number.isFinite(station.longitude) &&
          station.latitude >= -90 &&
          station.latitude <= 90 &&
          station.longitude >= -180 &&
          station.longitude <= 180,
      ),
    [stations],
  );

  const selectedStation = useMemo(
    () =>
      validStations.find(
        (station) => station.stationcode === selectedStationCode,
      ),
    [validStations, selectedStationCode],
  );

  return (
    <div className="relative h-[520px] overflow-hidden rounded-xl">
      <MapContainer
        center={PARIS_CENTER}
        zoom={12}
        scrollWheelZoom
        className="h-full w-full"
        zoomControl
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapFocus station={selectedStation} />

        {validStations.map((station) => {
          const selected =
            station.stationcode === selectedStationCode;
          const pct = emptyPctByStation[station.stationcode];
          const value = mode === "electric" ? (station.electric_bikes ?? 0) : station.bikes_available;
          const color = mode === "empty"
            ? (pct === undefined ? "#64748b" : pct >= 50 ? "#fb7185" : pct >= 20 ? "#fbbf24" : "#34d399")
            : markerColor(value);

          return (
            <CircleMarker
              key={station.stationcode}
              center={[station.latitude, station.longitude]}
              eventHandlers={{ click: () => onSelectStation?.(station.stationcode) }}
              radius={selected ? 10 : 5}
              pathOptions={{
                color: selected ? "#ffffff" : color,
                fillColor: color,
                fillOpacity: selected ? 1 : 0.8,
                weight: selected ? 3 : 1,
              }}
            >
              <Tooltip direction="top" opacity={0.95}>
                <div>
                  <strong>{station.name}</strong>
                  <br />
                  {mode === "empty" ? (pct === undefined ? "No historical data" : `${pct}% observed empty`) : mode === "electric" ? `${station.electric_bikes ?? "Unknown"} electric bikes` : `${station.bikes_available} bikes available`}
                </div>
              </Tooltip>

              <Popup>
                <div className="min-w-[190px]">
                  <h3 className="mb-2 text-base font-bold">
                    {station.name}
                  </h3>

                  <p>
                    🚲 Bikes: <strong>{station.bikes_available}</strong>
                  </p>

                  <p>
                    ⚡ Electric:{" "}
                    <strong>{station.electric_bikes ?? "Unknown"}</strong>
                  </p>

                  <p>
                    🅿️ Docks: <strong>{station.docks_available}</strong>
                  </p>

                  <p className="mt-2 text-xs text-gray-500">
                    Station {station.stationcode}
                  </p>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

      <div className="pointer-events-none absolute bottom-5 left-5 z-[1000] rounded-xl border border-white/10 bg-[#111c2c]/95 p-4 text-xs text-white shadow-xl">
        <p className="mb-3 font-semibold">{mode === "empty" ? "Observed empty frequency" : mode === "electric" ? "Electric bike availability" : "Bike availability"}</p>

        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-emerald-400" />
            {mode === "empty" ? "Under 20% empty" : "4+ bikes"}
          </div>

          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-amber-400" />
            {mode === "empty" ? "20–49% empty" : "1–3 bikes"}
          </div>

          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-red-400" />
            {mode === "empty" ? "50%+ empty" : "0 bikes"}
          </div>
        </div>
      </div>
    </div>
  );
}
