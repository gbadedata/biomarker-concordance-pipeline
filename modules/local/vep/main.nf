process VEP {
    tag "${meta.id}"
    label 'process_medium'
    container 'nfcore/vep:110.0'

    input:
    tuple val(meta), path(vcf), path(tbi)
    val   genome
    val   species
    val   cache_version
    path  vep_cache

    output:
    tuple val(meta), path('*.vep.vcf.gz'),       emit: vcf
    tuple val(meta), path('*.vep.vcf.gz.tbi'),   emit: tbi
    tuple val(meta), path('*.vep_summary.html'),  emit: report
    path 'versions.yml',                          emit: versions

    script:
    def prefix    = meta.id
    def cache_cmd = vep_cache ? "--dir_cache ${vep_cache}" : "--database"
    """
    vep \\
        --input_file ${vcf} \\
        --output_file ${prefix}.vep.vcf \\
        --format vcf --vcf \\
        --species ${species} \\
        --assembly ${genome} \\
        --cache --cache_version ${cache_version} \\
        ${cache_cmd} \\
        --fork ${task.cpus} \\
        --stats_file ${prefix}.vep_summary.html \\
        --everything --filter_common --per_gene --offline

    bgzip --threads ${task.cpus} ${prefix}.vep.vcf
    tabix -p vcf ${prefix}.vep.vcf.gz

    cat <<-VERSIONS > versions.yml
    "${task.process}":
        ensemblvep: \$(vep --help 2>&1 | grep 'Versions:' -A1 | tail -1 | awk '{print \$NF}')
    VERSIONS
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}.vep.vcf.gz ${prefix}.vep.vcf.gz.tbi ${prefix}.vep_summary.html
    cat <<-VERSIONS > versions.yml
    "${task.process}":
        ensemblvep: 110.0
    VERSIONS
    """
}
