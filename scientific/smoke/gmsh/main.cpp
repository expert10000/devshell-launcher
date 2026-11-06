#include <gmsh.h>
#include <iostream>

int main() {
    try {
        gmsh::initialize();
        gmsh::model::add("devshell-link-smoke");
        gmsh::model::occ::addRectangle(0., 0., 0., 1., 1.);
        gmsh::model::occ::synchronize();
        gmsh::model::mesh::generate(2);
        std::vector<std::size_t> nodes;
        std::vector<double> coordinates, parameters;
        gmsh::model::mesh::getNodes(nodes, coordinates, parameters);
        gmsh::finalize();
        if (nodes.size() < 4 || coordinates.size() != nodes.size() * 3) return 2;
        std::cout << "gmsh C++ surface nodes: " << nodes.size() << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        try { gmsh::finalize(); } catch (...) {}
        return 1;
    }
}
