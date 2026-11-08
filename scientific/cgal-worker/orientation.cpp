#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/boost/graph/IO/polygon_mesh_io.h>
#include <CGAL/boost/graph/helpers.h>
#include <CGAL/Polygon_mesh_processing/connected_components.h>
#include <CGAL/Polygon_mesh_processing/measure.h>
#include <CGAL/Polygon_mesh_processing/orientation.h>
#include <CGAL/Polygon_mesh_processing/self_intersections.h>
#include <CGAL/Polygon_mesh_processing/shape_predicates.h>
#include <CGAL/version.h>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace PMP = CGAL::Polygon_mesh_processing;
using Kernel = CGAL::Exact_predicates_inexact_constructions_kernel;
using Mesh = CGAL::Surface_mesh<Kernel::Point_3>;

static std::string quote(const std::string& value) {
  std::ostringstream out; out << '"';
  for (unsigned char c : value) {
    if (c == '"' || c == '\\') out << '\\' << c;
    else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << unsigned(c) << std::dec;
    else out << c;
  }
  out << '"'; return out.str();
}

int main(int argc, char** argv) {
  if (std::filesystem::exists("results.json")) {
    std::cerr << "results.json already exists; use a fresh working directory\n";
    return 3;
  }
  std::string operation, before = "unavailable", after = "unavailable", error;
  bool closed = false, changed = false;
  std::size_t vertices = 0, faces = 0;
  double volume_before = 0, volume_after = 0;
  try {
    if (argc < 3) throw std::runtime_error("Usage: devshell_cgal_orientation inspect input.obj | orient input.obj output.obj");
    operation = argv[1];
    if ((operation == "inspect" && argc != 3) || (operation == "orient" && argc != 4)
        || (operation != "inspect" && operation != "orient"))
      throw std::runtime_error("Operation or argument count is not registered");
    const auto input = std::filesystem::u8path(argv[2]);
    if (!std::filesystem::is_regular_file(input) || input.extension() != ".obj"
        || std::filesystem::file_size(input) > 32 * 1024 * 1024)
      throw std::runtime_error("Input must be a bounded OBJ mesh");
    Mesh mesh;
    if (!CGAL::IO::read_polygon_mesh(input.u8string(), mesh) || mesh.is_empty()
        || !CGAL::is_valid_polygon_mesh(mesh) || !CGAL::is_triangle_mesh(mesh)
        || mesh.number_of_faces() > 100000)
      throw std::runtime_error("Input must be a readable triangle manifold within 100000 faces");
    for (auto face : mesh.faces())
      if (PMP::is_degenerate_triangle_face(face, mesh))
        throw std::runtime_error("Input has a degenerate triangle");
    if (PMP::does_self_intersect(mesh))
      throw std::runtime_error("Input has self-intersections");
    vertices = mesh.number_of_vertices(); faces = mesh.number_of_faces();
    closed = CGAL::is_closed(mesh);
    if (closed) {
      auto map = mesh.add_property_map<Mesh::Face_index, std::size_t>("f:component", 0).first;
      if (PMP::connected_components(mesh, map) != 1)
        throw std::runtime_error("Orientation requires one connected component");
      if (!PMP::does_bound_a_volume(mesh))
        throw std::runtime_error("Closed mesh does not bound one volume");
      before = PMP::is_outward_oriented(mesh) ? "outward" : "inward";
      volume_before = CGAL::to_double(PMP::volume(mesh));
      if (!std::isfinite(volume_before) || volume_before == 0)
        throw std::runtime_error("Oriented volume is zero or non-finite");
    } else before = "undetermined";
    after = before; volume_after = volume_before;
    if (operation == "orient") {
      if (!closed) throw std::runtime_error("Orientation repair requires a closed mesh");
      const auto output = std::filesystem::u8path(argv[3]);
      if (output.extension() != ".obj" || std::filesystem::exists(output))
        throw std::runtime_error("Output must be a new OBJ file");
      if (before == "inward") {
        PMP::reverse_face_orientations(mesh);
        changed = true;
      }
      if (!CGAL::is_valid_polygon_mesh(mesh) || !PMP::is_outward_oriented(mesh))
        throw std::runtime_error("Orientation repair did not produce an outward manifold");
      after = "outward";
      volume_after = CGAL::to_double(PMP::volume(mesh));
      if (!std::isfinite(volume_after) || volume_after <= 0)
        throw std::runtime_error("Orientation repair produced invalid volume");
      if (!CGAL::IO::write_polygon_mesh(output.u8string(), mesh, CGAL::parameters::stream_precision(17)))
        throw std::runtime_error("Could not write repaired OBJ mesh");
    }
  } catch (const std::exception& exception) { error = exception.what(); }
  std::ostringstream result; result << std::setprecision(17);
  result << "{\"schemaVersion\":1,\"operation\":" << quote(operation)
         << ",\"state\":" << quote(error.empty() ? "succeeded" : "failed")
         << ",\"closed\":" << (closed ? "true" : "false")
         << ",\"vertices\":" << vertices << ",\"faces\":" << faces
         << ",\"beforeOrientation\":" << quote(before)
         << ",\"afterOrientation\":" << quote(after)
         << ",\"orientationChanged\":" << (changed ? "true" : "false")
         << ",\"signedVolumeBefore\":" << volume_before
         << ",\"signedVolumeAfter\":" << volume_after
         << ",\"versions\":{\"cgal\":" << quote(CGAL_VERSION_STR)
         << "},\"error\":" << quote(error)
         << ",\"scope\":\"Single connected closed triangle volume for outward repair; open mesh inspection only\"}";
  std::ofstream file("results.json", std::ios::binary);
  file << result.str(); file.close();
  std::cout << result.str() << std::endl;
  if (!file) { std::cerr << "Could not persist results.json\n"; return 3; }
  return error.empty() ? 0 : 2;
}
