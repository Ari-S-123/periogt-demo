export const PROPERTY_DISPLAY: Record<string, { label: string; units: string }> = {
  eat: { label: "Atomization energy", units: "eV" },
  eps: { label: "Dielectric constant (ε)", units: "" },
  density: { label: "Density", units: "g/cm³" },
  tg: { label: "Glass transition temperature (Tg)", units: "K" },
  nc: { label: "Refractive index (nc)", units: "" },
  eea: { label: "Electron affinity", units: "eV" },
  eip: { label: "Ionization potential", units: "eV" },
  xi: { label: "Chi parameter", units: "" },
  cp: { label: "Heat capacity (Cp)", units: "J/(mol·K)" },
  e_amorph: { label: "Young's modulus (amorphous)", units: "GPa" },
  egc: { label: "Band gap (chain)", units: "eV" },
  egb: { label: "Band gap (bulk)", units: "eV" },
};

export const EXAMPLE_SMILES = [
  { smiles: "*CC*", name: "Polyethylene" },
  { smiles: "*CC(*)C", name: "Polypropylene" },
  { smiles: "*c1ccc(*)cc1", name: "Poly(p-phenylene)" },
  { smiles: "*CC(*)c1ccccc1", name: "Polystyrene" },
  { smiles: "*CC(*)OC(=O)C", name: "Poly(vinyl acetate)" },
];

export const MAX_BATCH_SIZE = 100;
export const MAX_SMILES_LENGTH = 2000;
