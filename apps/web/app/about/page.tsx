import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PROPERTY_DISPLAY } from "@/lib/constants";

export default function AboutPage() {
  const properties = Object.entries(PROPERTY_DISPLAY);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">About PerioGT</h1>
        <p className="text-muted-foreground">
          Model information, supported properties, and citation details.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Model</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <p>
            <strong>PerioGT</strong> (Periodic Graph Transformer) is a
            graph-based deep learning model for polymer property prediction. It
            uses a pretrained graph transformer backbone with knowledge-augmented
            prompts from oligomer representations to predict various
            physicochemical properties of polymers from their repeat-unit SMILES.
          </p>
          <p>
            The model is pretrained on a large corpus of polymer structures and
            finetuned on individual property datasets. During inference, a
            polymer SMILES is converted into a molecular graph, augmented with
            oligomer-based embeddings, and passed through the transformer to
            produce property predictions or embedding vectors.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Supported Properties</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Property</TableHead>
                <TableHead>Units</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {properties.map(([id, info]) => (
                <TableRow key={id}>
                  <TableCell className="font-mono text-xs">{id}</TableCell>
                  <TableCell>{info.label}</TableCell>
                  <TableCell>{info.units || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Citation</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-2">
          <p>
            If you use PerioGT or its predictions in your research, please cite
            the original paper:
          </p>
          <pre className="rounded-md bg-muted p-4 text-xs overflow-auto whitespace-pre-wrap">
            {`@article{periogt2024,
  title={PerioGT: Periodic Table Guided Graph Transformer for Polymer Property Prediction},
  year={2024},
  note={Zenodo: https://zenodo.org/records/17035498}
}`}
          </pre>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Limitations</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-2">
          <ul className="list-disc pl-5 space-y-1">
            <li>
              Predictions are for homopolymer repeat units only (requires
              exactly two &apos;*&apos; connection points in the SMILES).
            </li>
            <li>
              Model accuracy varies by property and is limited by the training
              data distribution.
            </li>
            <li>
              Extrapolation beyond the training domain (novel chemistries) may
              produce unreliable predictions.
            </li>
            <li>
              This is a research prototype and should not be used as the sole
              basis for critical materials design decisions.
            </li>
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>License</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <p>
            Model artifacts (checkpoints, source code) are available from{" "}
            <a
              href="https://zenodo.org/records/17035498"
              className="underline underline-offset-2"
              target="_blank"
              rel="noopener noreferrer"
            >
              Zenodo (record 17035498)
            </a>{" "}
            under the CC-BY 4.0 license.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
