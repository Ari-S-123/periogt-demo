"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Form, FormField, FormItem, FormMessage } from "@/components/ui/form";
import { SmilesInput } from "@/components/smiles-input";
import { PropertySelector } from "@/components/property-selector";
import { PredictionResult } from "@/components/prediction-result";
import { useProperties } from "@/hooks/use-properties";
import { api, ApiError } from "@/lib/api";
import { predictFormSchema } from "@/lib/schemas";
import type { PredictFormValues, PredictResponse } from "@/lib/schemas";

export default function PredictPage() {
  const {
    properties,
    loading: propertiesLoading,
    error: propertiesError,
  } = useProperties();
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  const form = useForm<PredictFormValues>({
    resolver: zodResolver(predictFormSchema),
    defaultValues: {
      smiles: "",
      property: "",
      return_embedding: false,
    },
    mode: "onTouched",
  });

  useEffect(() => {
    if (properties.length > 0 && !form.getValues("property")) {
      form.setValue("property", properties[0].id, { shouldValidate: true });
    }
  }, [properties, form]);

  async function onSubmit(data: PredictFormValues) {
    setApiError(null);
    setResult(null);

    try {
      const res = await api.predict(data);
      setResult(res);
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(err.detail.message);
      } else {
        setApiError("An unexpected error occurred.");
      }
    }
  }

  const isSubmitting = form.formState.isSubmitting;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Property Prediction
        </h1>
        <p className="text-muted-foreground">
          Predict a polymer property from its repeat-unit SMILES using PerioGT.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Input</CardTitle>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="smiles"
                render={({ field, fieldState }) => (
                  <FormItem>
                    <SmilesInput
                      value={field.value}
                      onChange={field.onChange}
                      onBlur={field.onBlur}
                      error={fieldState.error?.message}
                      disabled={isSubmitting}
                    />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="property"
                render={({ field }) => (
                  <FormItem>
                    <PropertySelector
                      properties={properties}
                      value={field.value}
                      onChange={field.onChange}
                      disabled={isSubmitting}
                      loading={propertiesLoading}
                    />
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="return_embedding"
                render={({ field }) => (
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="return-embedding"
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      disabled={isSubmitting}
                    />
                    <Label
                      htmlFor="return-embedding"
                      className="text-sm font-normal"
                    >
                      Also return graph embedding vector
                    </Label>
                  </div>
                )}
              />
              <Button
                type="submit"
                disabled={isSubmitting || propertiesLoading}
              >
                {isSubmitting ? "Predicting..." : "Predict"}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>

      {(apiError || propertiesError) && (
        <Alert variant="destructive">
          <AlertDescription>{apiError || propertiesError}</AlertDescription>
        </Alert>
      )}

      {result && <PredictionResult result={result} />}
    </div>
  );
}
