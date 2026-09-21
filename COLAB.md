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

The notebook starts with one 7B model because a free T4 has about 15 GB of VRAM.
Do not enable all three configured 7B/8B models together in one Colab session. Run
one model, download the results, then change the selected model and run another
benchmark if you want to compare models.

It uses `--math-shepherd-backend mock` for the first real proof run. Proof generation
is real; only the optional Math-Shepherd verifier is mocked because its separate 7B
model would compete for the same T4 memory. ChatGPT's blind evaluation is imported
afterward and becomes the manual evaluator in the canonical results file.
