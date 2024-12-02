# PCB designs

A monorepository of my PCB designs created with [KiCAD][kicad] 8.

## Layout and Workflow

Custom symbols and footprints are located in [`libraries`], which is shared
between PCB projects using [`${KIPRJMOD}`][docs-kiprjmod].

Individual PCB projects (e.g. `*.kicad_pro` and friends) are located within
subdirectories, typically within [`dev`][dir-dev] or [`pcb`][dir-pcb].

When a PCB is ordered from a project, fabrication outputs are created and
in the project's `fab` subdirectory and committed to the repository.

## Setup

Ensure [pipx][pipx] is installed:

```sh
pip install pipx
```

Install [scons][scons]:

```sh
pipx install scons
```

Install KiCAD-related dependencies using the system site packages directory:

```sh
pipx install --system-site-packages kikit interactivehtmlbom
```

## Build

To render all outputs, simply run `scons`.

To render outputs for a particular board, run `scons -u` within that board's
project subdirectory.

## Licenses

Individual hardware designs in this repository may use different licenses.
The following licenses apply unless an included design directory specifies
different license(s).

* Hardware materials and designs are licensed under [CERN Open Hardware License
  version 2.0 Permissive (CERN-OHL-P v2)][license-cern-ohl-p-2.0]
  ([text](/LICENSE.hardware)). The version control history of this repository
  serves as the changes file.
* Software is licensed under the
  [GNU General Public License v3.0 (GPL-3.0)][license-gpl-3.0]
  ([text](/LICENSE.software))
* All documentation is licensed under
  [Creative Commons Attribution-ShareAlike 4.0 International
  (CC-BY-SA-4.0)][license-cc-by-sa-4.0] ([text](/LICENSE.documentation))

The `lcsc` KiCAD [symbols][libraries-lcsc-symbols],
[footprints][libraries-lcsc-pretty], and [3D models][libraries-lcsc-3dshapes]
libraries were created using [easyeda2kicad][easyeda2kicad]
([pypi][easyeda2kicad-pypi]), which are from [LCSC][lcsc]. [More info about
easyeda2kicad][easyeda2kicad-post]


[dir-dev]: /dev
[dir-pcb]: /pcb
[docs-kiprjmod]: https://docs.kicad.org/8.0/it/pcbnew/pcbnew_footprints_and_libraries.html#fp-path-variable-substitution
[easyeda2kicad-post]: https://hackaday.com/2023/08/08/easyeda2kicad-never-draw-a-footprint-again/
[easyeda2kicad-pypi]: https://pypi.org/project/easyeda2kicad/
[easyeda2kicad]: https://github.com/uPesy/easyeda2kicad.py
[kicad]: https://kicad.org/
[lcsc]: https://lcsc.com
[libraries-lcsc-3dshapes]: /libraries/lcsc.3dshapes
[libraries-lcsc-pretty]: /libraries/lcsc.pretty
[libraries-lcsc-symbols]: /libraries/lcsc.kicad_sym
[license-cc-by-sa-4.0]: https://creativecommons.org/licenses/by-sa/4.0/
[license-cern-ohl-p-2.0]: https://ohwr.org/cern_ohl_p_v2.pdf
[license-gpl-3.0]: https://www.gnu.org/licenses/gpl-3.0.html
[pipx]: https://pipx.pypa.io
[scons]: https://www.scons.org
