# Run the benchmark in Google Colab

Use the ready-made notebook at
[`notebooks/llm_proof_benchmark_colab.ipynb`](notebooks/llm_proof_benchmark_colab.ipynb).
In Colab, select **Runtime → Change runtime type → T4 GPU** before starting.

The notebook has a Markdown explanation before every code cell. Run the cells in
order. They do the following:

1. Clone or update this repository in Colab's temporary `/content` storage.
2. Confirm that PyTorch can access the T4 GPU.
3. Install this project plus the packages needed for 4-bit model loading.
4. Configure one 7B model (`deepseek-r1-distill-qwen-7b`) for 4-bit GPU inference.
5. Generate a real proof for theorem `T001`, create the blind ChatGPT bundle, and
   write the evaluations JSON and Excel workbook. The first run downloads the model
   into the Colab runtime.
6. Download the blind Markdown bundle, upload it to ChatGPT for anonymous scoring,
   and import ChatGPT's JSON response.
7. Download a zip archive containing the proof, evaluations, report, and workbook.

`/content` is deleted when the Colab runtime resets. Download the final archive (or
copy it to Google Drive with the optional notebook cell) before ending a session.
The model download stays in the Colab runtime cache only; it does not use storage on
your computer.

## Reading output

This preview:

```python
print(bundle_file.read_text()[:3000])
```

explicitly asks Python for only the first 3,000 characters. It is not a Colab output
limit. The notebook intentionally prints short previews and downloads full artifacts
as files, which is more reliable than rendering long proof bundles in a notebook
output area.

## Resource choice

The notebook has a ready-made selector for each model and an optional all-model
configuration. A free T4 has about 15 GB of VRAM, so models cannot remain loaded
together. The benchmark handles an all-model run safely by loading one 4-bit model,
generating its proof, unloading it and clearing GPU memory, then proceeding to the
next model. The separate Math-Shepherd checkpoint is loaded only after generation.
The initial all-model run needs roughly 55–60 GB in Colab's temporary runtime
storage and can take a substantial amount of time.

It uses the real `transformers` Math-Shepherd backend after proof generation. The
generator is unloaded first; Math-Shepherd then loads separately in 4-bit mode on the
T4 and produces per-step process-reward scores. ChatGPT's blind evaluation is
imported afterward as an independent manual evaluation in the same canonical results
file.
