# Prediction by Partial Matching (PPM)

Prediction by Partial Matching (PPM) is an adaptive statistical data compression technique that predicts the next symbol in a stream based on a set of previous symbols (the "context"). First proposed by Cleary and Witten in 1984, it is highly effective for lossless compression of natural language text.

## Core Mechanism

- **Context Modeling:** The algorithm uses a Markov model of order *n*, where *n* is the number of previous symbols used for prediction.
- **Blending & Escape Symbols:** If a symbol has not been seen in the current *n*-order context, an escape symbol is emitted, and the algorithm "escapes" to a shorter *(n-1)* context to attempt a new prediction. This continues until a match is found or it reaches a default order-0 or order-(-1) context.
- **Arithmetic Coding:** The final predicted probabilities are typically processed using an arithmetic coder to produce the compressed output.

## Key Variants

- **PPMC:** A widely cited implementation by Alistair Moffat (1990) that became a standard benchmark for high compression ratios.
- **PPMd:** An optimized version by Dmitry Shkarin used by default in the RAR file format and available in 7-Zip.
- **PPM\*:** An unbounded variant that allows contexts of any length.
- **PPM-Decay:** A version that incorporates memory decay, often used in auditory cognition research to model how humans predict patterns.

## Applications

- **File Compression:** Used by default in RAR and available in 7z. Most ZIP archivers (WinZip, Info-ZIP) default to Deflate; PPM is not a registered ZIP compression method in the PKZIP Application Note or IANA ZIP registry.
- **Assistive Technology:** Powers Dasher, a gesture-based text-entry system for users with motor impairments.
- **Web Prefetching:** Used to predict the next webpage a user might visit to reduce loading times.

---

## Open-Source PPM Libraries

Several open-source libraries and implementations of PPM are available across different programming languages, ranging from high-performance C versions to research-focused Python and R packages.

### 1. High-Performance C/C++ Libraries

- **7-Zip / p7zip (PPMd):** The most widely used implementation is PPMd (Variant H and I), which is part of the open-source 7-Zip LZMA SDK. It is highly optimized for both speed and compression ratio.
- **PPMZ:** A specialized file-to-file compressor based on the PPM method, known for extremely high compression ratios, though it is slower and more memory-intensive.

### 2. Python Libraries

- **PyPPMd:** A Python binding for the C-based PPMd implementation from p7zip. It supports PPMd Variant H and Variant I and is suitable for high-performance applications.
- **ppmd-cffi:** Another Python wrapper using CFFI to interface with the p7zip PPMd code.
- **pyppm:** A native Python implementation of the PPM compression algorithm, useful for learning or projects where a pure Python solution is preferred.
- **Reference Arithmetic Coding:** Project Nayuki provides a clear, educational Python implementation of PPM combined with arithmetic coding.

### 3. Research & Data Mining Libraries

- **SPMF (Java):** An open-source data mining library that includes a PPM sequence prediction model. It is often used for predicting the next symbol in a sequence rather than just for file compression.
- **ppm (R Package):** A specialized package for auditory cognition research that implements variants like PPM-Decay, which models how human memory fades over time.

### 4. Other Implementations

- **rene-puschinger/ppm (C++):** A straightforward C++ implementation on GitHub designed for benchmarking against other compression tools like ZIP and 7-Zip.
- **ppm-c (C):** A student-led implementation from the Federal University of Paraiba, useful for those looking at the algorithm from an information theory perspective.
