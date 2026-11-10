#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/boost/graph/IO/polygon_mesh_io.h>
#include <CGAL/boost/graph/helpers.h>
#include <CGAL/Polygon_mesh_processing/border.h>
#include <CGAL/Polygon_mesh_processing/connected_components.h>
#include <CGAL/Polygon_mesh_processing/measure.h>
#include <CGAL/Polygon_mesh_processing/orientation.h>
#include <CGAL/Polygon_mesh_processing/self_intersections.h>
#include <CGAL/Polygon_mesh_processing/shape_predicates.h>
#include <CGAL/Polygon_mesh_processing/triangulate_hole.h>
#include <CGAL/version.h>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

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
  std::string error;
  std::size_t before_faces = 0, after_faces = 0, boundary_edges = 0, patch_faces = 0;
  double volume_after = 0;
  try {
    if (argc != 4 || std::string(argv[1]) != "fill-one-hole")
      throw std::runtime_error("Usage: devshell_cgal_hole_repair fill-one-hole input.obj output.obj");
    const auto input = std::filesystem::u8path(argv[2]);
    const auto output = std::filesystem::u8path(argv[3]);
    if (!std::filesystem::is_regular_file(input) || input.extension() != ".obj"
        || std::filesystem::file_size(input) > 32 * 1024 * 1024)
      throw std::runtime_error("Input must be a bounded OBJ mesh");
    if (output.extension() != ".obj" || std::filesystem::exists(output))
      throw std::runtime_error("Output must be a new OBJ file");
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
    auto components = mesh.add_property_map<Mesh::Face_index, std::size_t>("f:component", 0).first;
    if (PMP::connected_components(mesh, components) != 1)
      throw std::runtime_error("Hole repair requires one connected component");
    before_faces = mesh.number_of_faces();
    std::vector<Mesh::Halfedge_index> cycles;
    PMP::extract_boundary_cycles(mesh, std::back_inserter(cycles));
    if (cycles.size() != 1)
      throw std::runtime_error("Hole repair requires exactly one boundary loop");
    auto current = cycles.front();
    do {
      ++boundary_edges;
      if (boundary_edges > 3) break;
      current = next(current, mesh);
    } while (current != cycles.front());
    if (boundary_edges != 3 || current != cycles.front())
      throw std::runtime_error("Hole repair requires a three-edge boundary");
    std::vector<Mesh::Face_index> patch;
    PMP::triangulate_hole(mesh, cycles.front(),
                          CGAL::parameters::face_output_iterator(std::back_inserter(patch)));
    patch_faces = patch.size();
    after_faces = mesh.number_of_faces();
    if (patch_faces != 1 || after_faces != before_faces + 1 || !CGAL::is_closed(mesh)
        || !CGAL::is_valid_polygon_mesh(mesh))
      throw std::runtime_error("Hole fill did not close exactly one triangular face");
    for (auto face : mesh.faces())
      if (PMP::is_degenerate_triangle_face(face, mesh))
        throw std::runtime_error("Hole fill produced a degenerate triangle");
    if (PMP::does_self_intersect(mesh) || !PMP::does_bound_a_volume(mesh)
        || !PMP::is_outward_oriented(mesh))
      throw std::runtime_error("Hole fill did not produce an outward bounded volume");
    volume_after = CGAL::to_double(PMP::volume(mesh));
    if (!std::isfinite(volume_after) || volume_after <= 0)
      throw std::runtime_error("Hole fill produced invalid volume");
    if (!CGAL::IO::write_polygon_mesh(output.u8string(), mesh, CGAL::parameters::stream_precision(17)))
      throw std::runtime_error("Could not write repaired OBJ mesh");
  } catch (const std::exception& exception) { error = exception.what(); }
  std::ostringstream result; result << std::setprecision(17);
  result << "{\"schemaVersion\":1,\"recipeId\":\"cgal.fill-one-hole\",\"state\":"
         << quote(error.empty() ? "succeeded" : "failed")
         << ",\"exitCode\":" << (error.empty() ? 0 : 2)
         << ",\"beforeFaces\":" << before_faces << ",\"afterFaces\":" << after_faces
         << ",\"boundaryEdgesBefore\":" << boundary_edges << ",\"patchFaces\":" << patch_faces
         << ",\"signedVolumeAfter\":" << volume_after
         << ",\"versions\":{\"cgal\":" << quote(CGAL_VERSION_STR)
         << "},\"error\":" << quote(error)
         << ",\"scope\":\"One connected triangle manifold with exactly one three-edge boundary; no general hole repair\"}";
  std::ofstream file("results.json", std::ios::binary); file << result.str(); file.close();
  std::cout << result.str() << std::endl;
  if (!file) { std::cerr << "Could not persist results.json\n"; return 3; }
  return error.empty() ? 0 : 2;
}
