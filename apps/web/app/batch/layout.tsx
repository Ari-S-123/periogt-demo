import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Batch Prediction — PerioGT",
  description:
    "Upload a CSV of polymer SMILES to predict properties in bulk using PerioGT.",
};

export default function BatchLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return children;
}
