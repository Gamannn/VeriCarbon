export interface GeoJSONPolygon {
  type: "Polygon"
  coordinates: number[][][]
}

export interface SubmissionForm {
  project_id: string
  name: string
  organization: string
  description: string
  claimed_area_ha: string
}

export interface VerificationResult {
  outcome: "VERIFIED" | "REQUIRES_REVIEW" | "REJECT"
  mode: "fixture" | "synthetic" | "live"
  confidence_bps: number
  estimated_vegetated_area_ha: number
  claimed_area_ha: number
  ndvi_mean: number
  ndvi_forest_fraction: number
  scenes: string[]
  dataset_hash: string
  model_hash: string
  result_hash: string
  notes: string[]
}

export interface SimilarityFeatures {
  cell_overlap_ratio: number
  polygon_overlap_ratio: number
  polygon_iou: number
  name_similarity: number
  org_similarity: number
  description_similarity: number
  area_similarity: number
  centroid_distance_m: number
}

export interface DuplicateMatch {
  other_id: string
  other_registry: string
  other_registry_ref: string
  risk_score: number
  risk_level: "LOW" | "MEDIUM" | "HIGH"
  features: SimilarityFeatures
  explanation: string[]
}

export interface DuplicateResult {
  highest_risk_level: "LOW" | "MEDIUM" | "HIGH"
  matches: DuplicateMatch[]
  cell_count: number
}

export interface OnchainResult {
  ok: boolean
  data: {
    tx?: { tx_hash: string; gas_used: number; block_number: number }
    cell_count?: number
    error?: string
    detail?: string
  }
}

export interface AttestResult {
  tx_hash: string
}

export interface ProjectState {
  state: "None" | "Pending" | "Flagged" | "Verified" | "Issued" | "Rejected"
  attestation_count: number
  verified_area_ha: number
  confidence_bps: number
}

export interface ChainStatus {
  configured: boolean
  chain_id?: number
  contract_address?: string
}

export interface RegistryEntry {
  polygon: GeoJSONPolygon
  name: string
  project_id: string
  registry?: string
}

export type LatLng = [number, number]

export const TEMPLATES = [
  {
    id: "near-amazonia",
    name: "Overlapping with Amazonia registry",
    description: "Expect HIGH risk — overlaps existing Amazonia entry",
    poly: [[-3.005, -60.015], [-3.005, -59.985], [-2.985, -59.985], [-2.985, -60.015]] as LatLng[],
  },
  {
    id: "near-kalimantan",
    name: "Near Kalimantan peat registry",
    description: "Expect MEDIUM risk — near Kalimantan entry",
    poly: [[-1.515, 113.805], [-1.515, 113.825], [-1.495, 113.825], [-1.495, 113.805]] as LatLng[],
  },
  {
    id: "unrelated-east-africa",
    name: "Fresh land in East Africa",
    description: "Expect LOW risk — no nearby registry entries",
    poly: [[-1.30, 36.80], [-1.30, 36.84], [-1.26, 36.84], [-1.26, 36.80]] as LatLng[],
  },
] as const
