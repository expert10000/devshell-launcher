#include <CGAL/Simple_cartesian.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/version.h>
#include <fstream>
#include <iostream>

int main() {
    using Kernel = CGAL::Simple_cartesian<double>;
    CGAL::Surface_mesh<Kernel::Point_3> mesh;
    const auto a = mesh.add_vertex({0, 0, 0});
    const auto b = mesh.add_vertex({1, 0, 0});
    const auto c = mesh.add_vertex({0, 1, 0});
    if (mesh.add_face(a, b, c) == decltype(mesh)::null_face()) return 2;
    std::ofstream geometry("triangle.off");
    geometry << "OFF\n3 1 0\n0 0 0\n1 0 0\n0 1 0\n3 0 1 2\n";
    geometry.close();
    if (!geometry) return 3;
    std::ofstream result("results.json");
    result << "{\"schemaVersion\":1,\"state\":\"succeeded\",\"runtime\":\"cgal\",\"version\":\""
           << CGAL_VERSION_STR << "\",\"vertices\":" << mesh.number_of_vertices()
           << ",\"faces\":" << mesh.number_of_faces() << ",\"artifact\":\"triangle.off\"}\n";
    if (!result) return 4;
    std::cout << "CGAL " << CGAL_VERSION_STR << ": Surface_mesh triangle, 3 vertices / 1 face\n";
    return 0;
}
