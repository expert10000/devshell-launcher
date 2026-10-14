#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/boost/graph/IO/polygon_mesh_io.h>
#include <CGAL/boost/graph/helpers.h>
#include <CGAL/Polygon_mesh_processing/triangulate_faces.h>
#include <CGAL/Polygon_mesh_processing/shape_predicates.h>
#include <CGAL/Polygon_mesh_processing/self_intersections.h>
#include <CGAL/Polygon_mesh_processing/remesh.h>
#include <CGAL/version.h>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
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
static double real(const char* text) {
  std::size_t used = 0; const std::string value(text);
  const double result = std::stod(value, &used);
  if (used != value.size() || !std::isfinite(result)) throw std::runtime_error("Expected a finite number");
  return result;
}
static std::string stats(const Mesh& mesh) {
  std::size_t boundary = 0;
  for (auto edge : mesh.edges()) if (CGAL::is_border(edge, mesh)) ++boundary;
  std::ostringstream out;
  out << "{\"vertices\":" << mesh.number_of_vertices() << ",\"edges\":" << mesh.number_of_edges()
      << ",\"faces\":" << mesh.number_of_faces() << ",\"boundaryEdges\":" << boundary
      << ",\"closed\":" << (CGAL::is_closed(mesh) ? "true" : "false") << '}';
  return out.str();
}
int main(int argc, char** argv) {
  const auto started = std::chrono::steady_clock::now();
  std::string operation, before = "null", after = "null", error;
  bool triangulated = false, self_intersection = false;
  std::size_t degenerates = 0;
  try {
    if (argc != 7) throw std::runtime_error("Usage: devshell_cgal_worker validate|remesh input output.obj target-edge iterations preserve-boundary(0|1)");
    operation = argv[1];
    if (operation != "validate" && operation != "remesh") throw std::runtime_error("Operation is not registered");
    const auto input = std::filesystem::u8path(argv[2]);
    const auto output = std::filesystem::u8path(argv[3]);
    if (!std::filesystem::is_regular_file(input) || std::filesystem::file_size(input) > 32 * 1024 * 1024)
      throw std::runtime_error("Input is missing or exceeds 32 MiB");
    if (output.extension() != ".obj" || std::filesystem::exists(output)) throw std::runtime_error("Output must be a new OBJ file");
    Mesh mesh;
    // Deliberately use plain IO: no implicit polygon-soup repair or orientation.
    if (!CGAL::IO::read_polygon_mesh(input.u8string(), mesh) || mesh.is_empty() || !CGAL::is_valid_polygon_mesh(mesh))
      throw std::runtime_error("Input is not a readable manifold polygon mesh; no automatic repair was attempted");
    if (mesh.number_of_faces() > 100000) throw std::runtime_error("Input exceeds the 100000-face laboratory limit");
    before = stats(mesh);
    if (!CGAL::is_triangle_mesh(mesh)) {
      if (!PMP::triangulate_faces(mesh)) throw std::runtime_error("Triangulation failed");
      triangulated = true;
    }
    for (auto face : mesh.faces()) if (PMP::is_degenerate_triangle_face(face, mesh)) ++degenerates;
    if (!degenerates) self_intersection = PMP::does_self_intersect(mesh);
    if (degenerates || self_intersection) throw std::runtime_error("Degenerate triangles or self-intersections detected; no repair was attempted");
    if (operation == "remesh") {
      const double target = real(argv[4]), iterations = real(argv[5]);
      const std::string preserve(argv[6]);
      if (target <= 0 || target > 1000000 || iterations < 1 || iterations > 10 || std::floor(iterations) != iterations || (preserve != "0" && preserve != "1"))
        throw std::runtime_error("Invalid remesh parameters");
      double low[3] = {INFINITY, INFINITY, INFINITY}, high[3] = {-INFINITY, -INFINITY, -INFINITY};
      for (auto vertex : mesh.vertices()) {
        const auto& point = mesh.point(vertex);
        const double coords[] = {CGAL::to_double(point.x()), CGAL::to_double(point.y()), CGAL::to_double(point.z())};
        for (int i = 0; i < 3; ++i) {
          if (!std::isfinite(coords[i])) throw std::runtime_error("Non-finite coordinates");
          low[i] = (std::min)(low[i], coords[i]); high[i] = (std::max)(high[i], coords[i]);
        }
      }
      double diagonal_squared = 0;
      for (int i = 0; i < 3; ++i) diagonal_squared += (high[i]-low[i])*(high[i]-low[i]);
      if (!std::isfinite(diagonal_squared) || 8 * diagonal_squared / (target * target) > 1000000)
        throw std::runtime_error("Target edge is too small for the conservative laboratory budget; use a larger value");
      const bool protect = preserve == "1";
      if (protect) {
        std::vector<Mesh::Edge_index> border;
        for (auto edge : mesh.edges()) if (CGAL::is_border(edge, mesh)) border.push_back(edge);
        PMP::split_long_edges(border, target, mesh);
      }
      PMP::isotropic_remeshing(mesh.faces(), target, mesh,
        CGAL::parameters::number_of_iterations(static_cast<unsigned>(iterations)).protect_constraints(protect));
      if (!CGAL::is_valid_polygon_mesh(mesh)) throw std::runtime_error("Remeshing produced an invalid graph");
    }
    after = stats(mesh);
    if (!CGAL::IO::write_polygon_mesh(output.u8string(), mesh, CGAL::parameters::stream_precision(17)))
      throw std::runtime_error("Could not write output mesh");
  } catch (const std::exception& exception) { error = exception.what(); }
  const auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-started).count();
  std::ostringstream result;
  result << "{\"schemaVersion\":1,\"runtimeId\":\"cgal-win-conda\",\"recipeId\":" << quote("cgal."+operation)
         << ",\"state\":" << quote(error.empty()?"succeeded":"failed") << ",\"exitCode\":" << (error.empty()?0:2)
         << ",\"durationMs\":" << duration << ",\"versions\":{\"cgal\":" << quote(CGAL_VERSION_STR)
         << "},\"before\":" << before << ",\"after\":" << after << ",\"triangulated\":" << (triangulated?"true":"false")
         << ",\"degenerateTriangles\":" << degenerates << ",\"selfIntersections\":" << (degenerates?"null":(self_intersection?"true":"false"))
         << ",\"error\":" << quote(error) << ",\"scope\":\"Manifold importer, triangulation, degenerate triangles and self-intersections; no soup repair or Boolean operation. Boundary protection may insert vertices.\"}";
  std::ofstream file("results.json", std::ios::binary); file << result.str(); file.close();
  std::cout << result.str() << std::endl;
  if (!file) { std::cerr << "Could not persist results.json\n"; return 3; }
  return error.empty()?0:2;
}
