#include <CGAL/AABB_face_graph_triangle_primitive.h>
#include <CGAL/AABB_traits_3.h>
#include <CGAL/AABB_tree.h>
#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <CGAL/Polygon_mesh_processing/self_intersections.h>
#include <CGAL/Polygon_mesh_processing/shape_predicates.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/boost/graph/IO/polygon_mesh_io.h>
#include <CGAL/boost/graph/helpers.h>
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
using Primitive = CGAL::AABB_face_graph_triangle_primitive<Mesh>;
using Traits = CGAL::AABB_traits_3<Kernel, Primitive>;
using Tree = CGAL::AABB_tree<Traits>;

static std::string quote(const std::string& value) {
  std::ostringstream out; out << '"';
  for (unsigned char c : value) {
    if (c == '"' || c == '\\') out << '\\' << c;
    else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << unsigned(c) << std::dec;
    else out << c;
  }
  out << '"'; return out.str();
}

static double finite(const char* text) {
  std::size_t used = 0;
  const std::string value(text);
  const double result = std::stod(value, &used);
  if (used != value.size() || !std::isfinite(result) || std::abs(result) > 1000000)
    throw std::runtime_error("Query coordinate must be finite and within +/-1000000");
  return result;
}

int main(int argc, char** argv) {
  if (std::filesystem::exists("results.json")) {
    std::cerr << "results.json already exists; use a fresh working directory\n";
    return 3;
  }
  std::string error;
  std::ostringstream payload;
  payload << std::setprecision(17);
  try {
    if (argc != 5) throw std::runtime_error("Usage: devshell_cgal_query input.obj x y z");
    const auto input = std::filesystem::u8path(argv[1]);
    if (!std::filesystem::is_regular_file(input) || input.extension() != ".obj"
        || std::filesystem::file_size(input) > 32 * 1024 * 1024)
      throw std::runtime_error("Input must be a bounded OBJ mesh");
    const Kernel::Point_3 point(finite(argv[2]), finite(argv[3]), finite(argv[4]));
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
    Tree tree(mesh.faces().begin(), mesh.faces().end(), mesh);
    tree.accelerate_distance_queries();
    const auto closest = tree.closest_point(point);
    const double squared = CGAL::to_double(tree.squared_distance(point));
    if (!std::isfinite(squared) || squared < 0)
      throw std::runtime_error("AABB query returned a non-finite distance");
    payload << "{\"schemaVersion\":1,\"state\":\"succeeded\",\"query\":["
            << CGAL::to_double(point.x()) << ',' << CGAL::to_double(point.y()) << ','
            << CGAL::to_double(point.z()) << "],\"closestPoint\":["
            << CGAL::to_double(closest.x()) << ',' << CGAL::to_double(closest.y()) << ','
            << CGAL::to_double(closest.z()) << "],\"squaredDistance\":" << squared
            << ",\"distance\":" << std::sqrt(squared) << ",\"faces\":"
            << mesh.number_of_faces() << ",\"versions\":{\"cgal\":"
            << quote(CGAL_VERSION_STR) << "},\"scope\":\"Triangle manifold AABB surface distance; no signed inside/outside classification\"}";
  } catch (const std::exception& exception) {
    error = exception.what();
    payload.str(""); payload.clear();
    payload << "{\"schemaVersion\":1,\"state\":\"failed\",\"error\":"
            << quote(error) << ",\"scope\":\"Triangle manifold AABB surface distance\"}";
  }
  std::ofstream file("results.json", std::ios::binary);
  file << payload.str(); file.close();
  std::cout << payload.str() << std::endl;
  if (!file) { std::cerr << "Could not persist results.json\n"; return 3; }
  return error.empty() ? 0 : 2;
}
