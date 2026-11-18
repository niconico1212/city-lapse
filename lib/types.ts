export type Confidence = "documented" | "estimated" | "reconstructed";

export interface CityIndexEntry {
  slug: string;
  name: string;
  country: string;
  rank: number;
  population_2025: number;
  start_year: number;
  status: "ok" | "partial" | "missing";
  center: { lat: number; lon: number };
  un_name: string;
}

export interface CityIndex {
  ranking_source: { id: string; title: string; url: string; definition: string; ranked_by: string };
  cities: CityIndexEntry[];
}

export interface PopulationPoint {
  year: number;
  value: number;
  confidence: Confidence;
  source: string;
  note?: string;
  definition?: string;
  series?: string;
}

export interface Milestone {
  year: number;
  title: string;
  detail: string;
  source: string;
  confidence: Confidence;
}

export interface Landmark {
  name: string;
  year: number;
  height_m: number;
  lat: number;
  lon: number;
  kind: string;
  source: string;
  confidence: Confidence;
  demolished_year?: number;
  note?: string;
  /** metres east / north of the city centre */
  x: number;
  y: number;
}

export interface FootprintEpoch {
  year: number;
  area_km2: number;
  confidence: Confidence;
}

export interface CameraKey {
  year: number;
  x: number;
  y: number;
  r: number;
}

export interface CityData {
  slug: string;
  name: string;
  country: string;
  rank: number;
  un_name: string;
  population_2025: number;
  status: "ok" | "partial";
  status_reasons: string[];
  start_year: number;
  start_label: string;
  start_source: string;
  start_confidence: Confidence;
  end_year: number;
  center: { lat: number; lon: number };
  historic_core: { name: string; lat: number; lon: number; source: string };
  population: PopulationPoint[];
  milestones: Milestone[];
  landmarks: Landmark[];
  notes: string;
  footprint: {
    epochs: FootprintEpoch[];
    urban_centre: { id: number; name: string; area_km2: number };
    shared_urban_centre_split: { with: string; distance_weight: number; target_area_share: number } | null;
    reconstruction: {
      historic_core: { name: string; lat: number; lon: number; snapped_m: number };
      satellite_seeds: { distance_km: number }[];
      start_site?: { name: string; lat?: number; lon?: number; snapped_m?: number; unused?: string } | null;
      density_decline_per_year: number;
      density_peak_year: number;
      density_cap_per_ha: number;
      population_basis: string;
      density_1975_per_ha: number;
      first_population_year: number;
    };
    threshold_m2_per_cell: number;
    sources: { built_surface: string; building_height: string; extent: string };
  };
  buildings: {
    file: string;
    count: number;
    bytes: number;
    xy_scale: number;
    wd_unit: number;
    ground_unit: number;
    layout: string[];
    generic: number;
    landmark_parts: number;
    max_generic_height_m: number;
    cells: number;
    units: number;
    median_height_m: number;
  };
  camera: CameraKey[];
}
