"""Explicit offscreen rendering smoke check; owned by the bounded smoke runner."""
import json
import os
from pathlib import Path
import sys

handles = []
for folder in (Path(sys.prefix), Path(sys.prefix) / 'Library' / 'bin'):
    if hasattr(os, 'add_dll_directory') and folder.is_dir():
        handles.append(os.add_dll_directory(str(folder)))

from vtkmodules.vtkCommonCore import vtkVersion
from vtkmodules.vtkFiltersSources import vtkSphereSource
from vtkmodules.vtkIOImage import vtkPNGWriter
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer, vtkRenderWindow, vtkWindowToImageFilter
import vtkmodules.vtkRenderingOpenGL2

sphere = vtkSphereSource()
sphere.SetThetaResolution(32)
sphere.SetPhiResolution(24)
mapper = vtkPolyDataMapper()
mapper.SetInputConnection(sphere.GetOutputPort())
actor = vtkActor()
actor.SetMapper(mapper)
actor.GetProperty().SetColor(0.17, 0.72, 0.78)
renderer = vtkRenderer()
renderer.SetBackground(0.07, 0.10, 0.14)
renderer.AddActor(actor)
window = vtkRenderWindow()
window.SetOffScreenRendering(1)
window.SetSize(640, 480)
window.AddRenderer(renderer)
renderer.ResetCamera()
window.Render()
capture = vtkWindowToImageFilter()
capture.SetInput(window)
capture.ReadFrontBufferOff()
capture.Update()
image = capture.GetOutput()
if tuple(image.GetDimensions())[:2] != (640, 480):
    raise RuntimeError('Unexpected captured image dimensions')
scalars = image.GetPointData().GetScalars()
extent = scalars.GetRange(0)
if extent[1] - extent[0] < 10:
    raise RuntimeError('Rendered image appears blank')
writer = vtkPNGWriter()
writer.SetFileName('vtk-offscreen.png')
writer.SetInputConnection(capture.GetOutputPort())
writer.Write()
output = Path('vtk-offscreen.png')
if not output.is_file() or output.stat().st_size < 1000:
    raise RuntimeError('Rendered PNG missing or unexpectedly small')
result = {'schemaVersion': 1, 'state': 'succeeded', 'runtime': 'vtk',
          'version': vtkVersion.GetVTKVersion(), 'dimensions': [640, 480],
          'artifact': str(output), 'backend': window.GetClassName(),
          'capabilities': window.ReportCapabilities()[:16000]}
Path('results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
window.Finalize()
print(json.dumps(result))
