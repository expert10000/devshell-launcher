#include <vtkNew.h>
#include <vtkPolyData.h>
#include <vtkSphereSource.h>
#include <vtkVersion.h>
#include <vtkXMLPolyDataReader.h>
#include <vtkXMLPolyDataWriter.h>
#include <fstream>
#include <iostream>

int main() {
    vtkNew<vtkSphereSource> sphere;
    sphere->SetThetaResolution(24);
    sphere->SetPhiResolution(16);
    sphere->Update();
    vtkNew<vtkXMLPolyDataWriter> writer;
    writer->SetFileName("sphere.vtp");
    writer->SetInputConnection(sphere->GetOutputPort());
    if (writer->Write() != 1) return 2;
    vtkNew<vtkXMLPolyDataReader> reader;
    reader->SetFileName("sphere.vtp");
    reader->Update();
    auto* mesh = reader->GetOutput();
    if (mesh->GetNumberOfPoints() == 0 || mesh->GetNumberOfCells() == 0) return 3;
    std::ofstream result("results.json");
    result << "{\"schemaVersion\":1,\"state\":\"succeeded\",\"runtime\":\"vtk\",\"version\":\""
           << vtkVersion::GetVTKVersion() << "\",\"points\":" << mesh->GetNumberOfPoints()
           << ",\"cells\":" << mesh->GetNumberOfCells() << ",\"artifact\":\"sphere.vtp\"}\n";
    if (!result) return 4;
    std::cout << "VTK " << vtkVersion::GetVTKVersion() << ": sphere write/read, "
              << mesh->GetNumberOfPoints() << " points / " << mesh->GetNumberOfCells() << " cells\n";
    return 0;
}
