process GATK_GENOTYPEGVCFS {
    tag "${meta.id}"
    label 'process_medium'
    container 'broadinstitute/gatk:4.5.0.0'

    input:
    tuple val(meta), path(gvcf), path(tbi)
    path fasta
    path fasta_fai
    path fasta_dict
    path dbsnp
    path dbsnp_tbi

    output:
    tuple val(meta), path('*.vcf.gz'),     emit: vcf
    tuple val(meta), path('*.vcf.gz.tbi'), emit: tbi
    path 'versions.yml',                   emit: versions

    script:
    def prefix    = meta.id
    def avail_mem = (task.memory.giga * 0.8).intValue()
    """
    gatk --java-options "-Xmx${avail_mem}g" GenotypeGVCFs \\
        --variant ${gvcf} \\
        --reference ${fasta} \\
        --dbsnp ${dbsnp} \\
        --output ${prefix}.vcf.gz \\
        --tmp-dir .

    cat <<-VERSIONS > versions.yml
    "${task.process}":
        gatk: \$(gatk --version 2>&1 | grep -o '[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+' | head -1)
    VERSIONS
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}.vcf.gz ${prefix}.vcf.gz.tbi
    cat <<-VERSIONS > versions.yml
    "${task.process}":
        gatk: 4.5.0.0
    VERSIONS
    """
}
