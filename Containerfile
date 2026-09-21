# The toolchain a campaign needs, and nothing else. Build it; do not expect to pull it -- the
# binary `sib build` produces links GPL-3 code, so publishing an image would be distributing that,
# and NOTICE.md says why this repository does not.
#
#   podman build -t sib .
#   podman run --rm -v "$PWD:/w" -w /w sib sib build
#   podman run --rm -v "$PWD:/w" -w /w sib sib run --keys my_catalog.txt
#
# The volume matters: `build/` and `corpora/` are gigabytes and belong on your disk, not in a layer.
FROM docker.io/library/debian:trixie-slim

# One layer, no recommends, no apt cache: the image is a toolchain, not a system.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      cmake \
      curl \
      git \
      libboost-filesystem-dev \
      libboost-iostreams-dev \
      libboost-system-dev \
      libboost-test-dev \
      python3 \
      time \
      xz-utils \
      wamerican \
    && rm -rf /var/lib/apt/lists/*

# `words` is the one corpus read off the machine rather than fetched; `wamerican` above is what
# puts a dictionary at /usr/share/dict/words inside the image, so a campaign has all thirteen.

# rustup rather than Debian's rustc: the harness builds lexindex from crates.io, which tracks a
# recent stable, and a distribution's compiler is a moving constraint no pin here controls.
ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo PATH=/usr/local/cargo/bin:$PATH
RUN curl -fsSL https://sh.rustup.rs | sh -s -- -y --no-modify-path --profile minimal \
    && chmod -R a+w "$CARGO_HOME"

# `uv` is what `harness/run.sh` calls for the two Python steps. Pinned, because an installer script
# that resolves "latest" is the one unpinned thing in an otherwise pinned build.
RUN curl -fsSL https://astral.sh/uv/0.9.7/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# Nothing from this repository is copied in: the image is a toolchain, and the checkout arrives on
# a volume. Two copies of the harness -- one baked, one mounted -- is how a container ends up
# running code the reader is not looking at.
RUN printf '#!/bin/sh\nexec python3 "$(pwd)/sib/__main__.py" "$@"\n' > /usr/local/bin/sib \
    && chmod +x /usr/local/bin/sib

# `sib` resolves the harness relative to the working directory, so run it from the mounted checkout.
WORKDIR /w
CMD ["bash"]
